"""
Distributed Ray pipeline for parsing documents, generating embeddings and knowledge graphs, and indexing them into Qdrant and Neo4j
"""
import ray
import logging
from typing import Any, Dict

from pipelines.ingestion.embedding.compute import BatchEmbedder
from pipelines.ingestion.graph.extractor import GraphExtractor
from pipelines.ingestion.indexing.neo4j import Neo4jIndexer
from pipelines.ingestion.indexing.qdrant import QdrantIndexer

from pipelines.ingestion.chunking.metadata import enrich_metadata
from libs.utils.document_parsing import parse_document
from pipelines.ingestion.chunking.splitter import split_text

logger = logging.getLogger(__name__)

# Initialize Ray (Connect to the existing cluster)
ray.init(address="auto")

def process_batch(batch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ray Data transformation function.
    Receives a batch of file contents (S3 bytes) and converts them into text chunks
    """
    results  = []

    for i, content in enumerate(batch["content"]):
        filename = batch["filename"][i]

        try:
            # 1. Parsing (CPU Intensive)
            # We use a helper function to handle PDF/DOCX/HTML logic
            raw_text, metadata = parse_document(content, filename)

            # 2. Chunking (CPU)
            chunks= split_text(raw_text, chunk_size=512, overlap=50)

            # Add metadata to each chunk
            for chunk in chunks:
                chunk["metadata"].update(
                    enrich_metadata(metadata, chunk["text"])
                )
                results.append(chunk)
        
        except Exception as e:
            logger.error(f"Failed processing file {filename}: {e}")

    return {
        "text": [r["text"] for r in results], 
        "metadata": [r["metadata"] for r in results]
    }


def main(bucket_name: str, prefix: str):
    """
    Distributed ingestion pipeline orchestrated using Ray Data.
    """

    logger.info(f"Starting ingestion for s3://{bucket_name}/{prefix}")

    # 1. Read from S3 using Ray Data (Lazy Loading)
    # This automatically distributes reading across workers
    ds = ray.data.read_binary_files(
        paths=f"s3://{bucket_name}/{prefix}",
        include_path=True
    )

    logger.info("Files loaded from S3")

    # 2. Parse & Chunk (Map Phase)
    # num_cpus=1 tells Ray to reserve 1 CPU core per parsing task
    chunked_ds = ds.map_batches(
        process_batch,
        batch_size=10, # Process 10 files at a time per worker
        num_cpus=1
    )

    logger.info("Parsing and chunking stage configured")

    # 3. FORK: Branch A - Vector Embeddings (GPU Intensive)
    # We use a Class Actor (BatchEmbedder) to maintain connection to Ray Serve
    vector_ds = chunked_ds.map_batches(
        BatchEmbedder,
        concurrency=5, # Run 5 concurrent embedders
        num_gpus=0.2, # Each embedder needs minimal GPU access (Ray Serve handles heavy lift)
        batch_size=100 
    )

    logger.info("Embedding pipeline configured")

    # 4. FORK: Branch B - Graph Extraction (LLM Intensive)
    # This is slower, so we might set higher concurrency or dedicate nodes
    graph_ds = chunked_ds.map_batches(
        GraphExtractor,
        concurrency=10, 
        num_gpus=0.5,   # Needs significant LLM inference power
        batch_size=5
    )

    logger.info("Graph extraction pipeline configured")

    # 5. Indexing (Write to DBs)
    # Trigger execution

    logger.info("Writing embeddings to Qdrant")
    vector_ds.write_datasource(QdrantIndexer())

    logger.info("Writing graph data to Neo4j")
    graph_ds.write_datasource(Neo4jIndexer())

    logger.info("Ingestion job completed successfully.")


if __name__ == "__main__":
    # In a real run, these args come from the job submission
    import sys
    main(sys.argv[1], sys.argv[2])