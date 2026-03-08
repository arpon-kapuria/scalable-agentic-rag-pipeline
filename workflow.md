# Workflow

- [ ] Missing packages - vllm, PyTorch


### Dataset Preparation:
- [ ] Collect 950 random pdfs from this repo [https://github.com/tpn/pdfs.git] and put them into `noisy_data` folder
- [ ] Using a script, scrape open-source kubernetes official documentation and saved them in different formats such as pdf, docx, txt, html files in the `true_data` directory
- [ ] Merge both noisy and true data into a single `data` directory


### Data Storage Setup
- [ ] `Aurora Postgres` for chat history and metadata storage
- [ ] `Redis` for caching frequently accessed data
- [ ] `Qdrant` as our vector database for storing embeddings
- [ ] `Neo4j` as our graph database for storing relationships between entities
- [ ] `AWS S3` as our primary document storage along with clustered Ray serving for hosting our AI models (LLM, Embeddings, Rerankers)
- [ ] `MinIO` works as fake AWS S3 for local development


### Setup Development Workflow
- [x] `.env` file to share environment variables required for local development.
- [x] `Makefile` to automate common tasks such as building, testing and deploying the application
- [x] `docker-compose.yaml` file to define all the services required to run the entire rag pipeline locally using Docker containers
- [x] Create shared utilies files `(ids.py, timing.py, backoff.py, document_parsing.py)`
- [ ] Setup configurations file in `services/api/app/config.py` file

> `docker-compose.yaml` file pulls and runs the 5 services `(pgsql, redis, qdrant, neo4j, minio)` and uv runs the fastapi app. It simulates everything locally. No need to install those services.


### Data Ingestion Layer
- [x] Setup Ray Data to distribute data ingestion process so that tasks can be processed parallely (creates DAG of taks)
- [x] Create separate loader files `(pdf.py, docx.py, html.py)`, where we use temporary files to handle memory efficiently
- [x] Split the raw text using `splitter.py` text into 512-token chunks (standard limit for many embedding models)
- [x] Enrich the chunk's base metadata by adding hash and timestamp for deduplication and freshness tracking in  `metadata.py`
- [x] Batch processing of text chunks to generate vector embeddings using Ray worker (GPU embedding service) in `compute.py`
- [x] Extract knowledge-graph relationships using `extractor.py` from the text chunks following the schema defined in `schema.py` file
- [x] Index embeddings into vector database `qdrant.py` for semantic vector search 
- [x] Index knowledge-graph nodes and relationships into graph database `neo4j.py` for entity relationship reasoning
- [x] Combine all the ingestion components in one file `ingestion/main.py` to process parallely
- [x] Setup `ray_job.yaml` as a manual trigger for Ray distributed ingestion pipeline during development and testing
- [x] Setup `s3_event_handler.py` as the production event-driven trigger — automatically submits an ingestion job to Ray when a file is uploaded to S3
- [x] Setup `bulk_upload_s3.py` script that scans a local directory and uploads all files to S3 in parallel using multipart upload with retries, automatically triggering the downstream ingestion pipeline via S3 events


### AI Compute Layer
- [x] Setup Ray Serve to host models as independent microservices that can auto scale based on GPU availability and traffic
- [x] Keep separate model configuration files for chat models, embedding models and rerankers in `services/api/app/models/` folder
- [x] Serve AI models with `vLLM` and embedding models & rerankers with `sentence_transformers`
- [x] Implement an async HTTP client used by the API server to communicate with the Ray-Serve LLM `ray_llm.py` & Embedding service `ray_embed.py`



> **Why vLLM instead of HuggingFace pipelines?**
> - **Higher throughput** – optimized for serving many concurrent requests.
> - **PagedAttention** – prevents GPU memory fragmentation in KV cache.
> - **Dynamic batching** – processes tokens from multiple requests together.
> - **Better GPU utilization** – supports far more simultaneous generations.
> - **Lower latency under load** – designed for production inference, not experimentation.