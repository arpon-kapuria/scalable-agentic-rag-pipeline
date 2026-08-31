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
        self._collections_ready = False

    # Lazy, not called from app startup — connects to Qdrant on first
    # actual use instead of unconditionally at boot. Keeps the app
    # bootable on whatever Docker profile is currently up (e.g. Phase 2's
    # core+cache, no vector profile), matching neo4j_client/embed_client's
    # existing lazy-connect pattern. Guarded by _collections_ready so
    # concurrent first-callers don't all race to create collections.
    async def init_collections(self):
        if self._collections_ready:
            return

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

        self._collections_ready = True

    async def search(self, query_vector: list[float], limit: int = 5):
        """
        Performs Semantic Search.
        """
        await self.init_collections()
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
        await self.init_collections()
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