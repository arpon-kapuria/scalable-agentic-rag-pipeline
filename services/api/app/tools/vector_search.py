import asyncio

from models.embeddings.fastembed_client import fastembed_client
from services.api.app.clients.embedding import embedding_client
from services.api.app.clients.qdrant import qdrant_client


async def search_vector_tool(query: str, corpus_id: str) -> str:
    """
    Tool: Search the Vector Database for documents, scoped to one
    corpus_id (never cross-tenant). Same hybrid dense+BM25/RRF path
    retriever_node uses, kept in sync rather than a second retrieval
    implementation for the manual tool-call path.
    """
    try:
        dense_vector, sparse_vector = await asyncio.gather(
            embedding_client.embed_query(query),
            asyncio.to_thread(fastembed_client.embed_sparse, [query]),
        )
        results = await qdrant_client.search_hybrid(
            dense_vector=dense_vector,
            sparse_vector=sparse_vector[0],
            corpus_id=corpus_id,
            limit=3,
        )

        if not results:
            return "No relevant documents found."

        formatted = ""
        for r in results:
            payload = r.payload or {}
            filename = payload.get("filename", "Unknown")
            page = payload.get("page", "N/A")
            formatted += f"- Content: {payload.get('text', '')[:200]}... [Source: {filename}, Page: {page}]\n"

        return formatted

    except Exception as e:
        return f"Search Error: {str(e)}"
