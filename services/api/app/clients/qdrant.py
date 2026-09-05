from qdrant_client import AsyncQdrantClient, models
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
            prefer_grpc=False
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

        # Main RAG collection — named vectors: "dense" (bge-large-en-v1.5,
        # 1024-dim) + "sparse" (FastEmbed's Qdrant/bm25 export), fused via
        # RRF at query time (see search_hybrid below). Size 1024 matches
        # the FastEmbed substitute for bge-m3 (see config.py comment —
        # bge-m3 isn't in FastEmbed's supported model set).
        if settings.QDRANT_COLLECTION not in existing:
            await self.client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
                sparse_vectors_config={"sparse": models.SparseVectorParams()},
            )

        # Semantic cache collection — untouched, Phase 5 (Redis Stack)
        # replaces this entirely per the locked design; left as-is so
        # Phase 5 owns the removal, not silently changed here.
        if "semantic_cache" not in existing:
            await self.client.create_collection(
                collection_name="semantic_cache",
                vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
            )

        self._collections_ready = True

    async def search_hybrid(
        self,
        dense_vector: list[float],
        sparse_vector: dict,
        corpus_id: str,
        limit: int = 10,
        rrf_k: int = 60,
    ):
        """
        Dense + BM25 sparse, fused via Qdrant's native RRF (Query API
        prefetch + fusion), filtered to one corpus_id — never cross-tenant.
        """
        await self.init_collections()
        response = await self.client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            prefetch=[
                models.Prefetch(query=dense_vector, using="dense", limit=limit),
                models.Prefetch(
                    query=models.SparseVector(indices=sparse_vector["indices"], values=sparse_vector["values"]),
                    using="sparse",
                    limit=limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=models.Filter(
                must=[models.FieldCondition(key="corpus_id", match=models.MatchValue(value=corpus_id))]
            ),
            limit=limit,
            with_payload=True,
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

    async def count_distinct_documents(self, corpus_id: str) -> int:
        """
        Powers the single-paper vs multi-paper retrieval routing decision
        (locked design: "single paper -> Qdrant only, multi-paper ->
        Qdrant + Neo4j"). Scroll is fine at demo scale — a dedicated
        documents table (Phase 6's corpus/documents endpoint) would be the
        right answer at real scale, but doesn't exist yet.
        """
        await self.init_collections()
        points, _ = await self.client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="corpus_id", match=models.MatchValue(value=corpus_id))]
            ),
            with_payload=["filename"],
            limit=1000,
        )
        return len({p.payload.get("filename") for p in points if p.payload})

    async def close(self):
        await self.client.close()

# Global instance
qdrant_client = VectorDBClient()
