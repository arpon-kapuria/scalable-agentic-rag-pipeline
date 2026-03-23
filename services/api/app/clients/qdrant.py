from qdrant_client import AsyncQdrantClient
from services.api.app.config import settings

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

    async def search(self, vector: list[float], limit: int = 5):
        """
        Performs Semantic Search.
        """
        return await self.client.search(
            # Uses approximate Nearest Neighbor with cosine similarity (default search unless mentioned)
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=vector,
            limit=limit,
            with_payload=True
        )

# Global instance
qdrant_client = VectorDBClient()