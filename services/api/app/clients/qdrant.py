from qdrant_client import AsyncQdrantClient
from services.api.app.config import settings

from qdrant_client.models import VectorParams, Distance

class VectorDBClient:
    """
    Async Client for Qdrant.
    """
    def __init__(self):
        self.client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            # In prod, we might enable gRPC for slightly faster performance
            prefer_grpc=True 
        )

    # On app startup → Qdrant collections are created automatically
    # MIGHT GET DELETED
    async def init_collections(self):
        collections = await self.client.get_collections()
        existing = {c.name for c in collections.collections}

        # Main RAG collection
        if settings.QDRANT_COLLECTION not in existing:
            await self.client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )

        # Semantic cache collection
        if "semantic_cache" not in existing:
            await self.client.create_collection(
                collection_name="semantic_cache",
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )

    async def search(self, query_vector: list[float], limit: int = 5):
        """
        Performs Semantic Search.
        """
        response = await self.client.query_points(
            # Uses approximate Nearest Neighbor with cosine similarity (default search unless mentioned)
            collection_name=settings.QDRANT_COLLECTION,
            query=query_vector,
            limit=limit,
            with_payload=True
        )

        return response.points
    
    # search method for semantic cache searches
    async def search_collection(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 1,
        score_threshold: float = 0.95
    ):
        response = await self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            score_threshold=score_threshold
        )
        return response.points

    async def close(self):
        await self.client.close()

# Global instance
qdrant_client = VectorDBClient()