"""
In-process embedding — replaces the old BatchEmbedder's HTTP call to a
Ray Serve endpoint that's frozen until Phase 11 and was never deployed
locally. Uses the same EmbeddingClient (FastEmbed primary, OpenRouter
fallback) the query-time chat path uses — "same code, both local and
cloud" per the locked design, not two separate embedding implementations.

Dense embedding goes through the async failover client (asyncio.run()
per batch — see graph/extractor.py for the same sync/async bridging
rationale). Sparse (BM25) stays direct/sync — FastEmbed's BM25 export is
a lightweight tokenizer-based computation, not a model inference likely
to fail, so no failover path is needed for it.
"""

import asyncio
from typing import Any, Dict

from models.embeddings.fastembed_client import fastembed_client
from services.api.app.clients.embedding import embedding_client


class BatchEmbedder:
    """Callable Class for Ray Data — one instance per actor, embed models load once."""

    def __call__(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        texts = list(batch["text"])
        batch["dense_vector"] = asyncio.run(embedding_client.embed_documents(texts))
        batch["sparse_vector"] = fastembed_client.embed_sparse(texts)
        return batch
