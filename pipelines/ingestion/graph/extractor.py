"""
Ray worker that sends text chunks to an LLM to extract knowledge-graph
entities/relationships, returning nodes/edges per chunk.

Batches multiple chunks into ONE LLM call (Bug 2 fix) instead of one call
per chunk — on a 122-chunk paper this was 122 sequential Groq calls,
producing 494 429s / 110 full-backend exhaustions in testing. Batching by
Ray's own batch_size (main.py sets batch_size=5 for this stage) cuts that
to ~1 call per 5 chunks with no separate config needed.

The LLM client (and its circuit breaker) is created ONCE per actor, in
__init__, and reused across every batch __call__ for that actor's whole
lifetime — NOT recreated per batch. This was a real bug in the first cut
of this file: a fresh client per batch meant a fresh (CLOSED) circuit
breaker every time too, so the "stop hammering during cooldown" mechanism
never actually engaged — every batch retried the full Groq->OpenRouter
sequence from scratch even while Groq was still fully exhausted,
producing a 27-minute ingestion run dominated by retry/backoff waits, not
real work. A persistent event loop (not asyncio.run() per call) is what
makes a persistent httpx.AsyncClient safe to reuse here — Ray actors are
long-lived processes, so one loop for the actor's life is the correct
pattern, not a new one per batch.

Output nodes/edges are JSON-STRING serialized, not native Python lists
(Bug 4 fix) — Ray Data batches are Arrow-backed, and a column of
ragged/mixed-shape object arrays (some rows [], others lists-of-dicts)
broke Arrow's type inference, silently falling back to slow pickled
serialization every batch. A plain string column has no such problem;
Neo4jIndexer json.loads()s it back.

Uses the Phase 1 LLMClient factory (Groq/OpenRouter failover, matching the
chat-response path) — not the dead Ray Serve LLM endpoint this originally
pointed at.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Tuple

from pipelines.ingestion.graph.schema import GraphSchema
from services.api.app.clients.llm.factory import build_llm_client

logger = logging.getLogger(__name__)


class GraphExtractor:
    """Ray Actor Class for Graph Extraction via the LLMClient factory."""

    def __init__(self):
        # One event loop + one client (+ its circuit breaker) for this
        # actor's entire lifetime — see module docstring for why this
        # matters (circuit breaker persistence, not just avoiding
        # per-call httpx client setup overhead).
        self._loop = asyncio.new_event_loop()
        self._client = build_llm_client()
        self._loop.run_until_complete(self._client.start())

    def __call__(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        texts = list(batch["text"])  # Ray batches are numpy arrays by default — see compute.py's same fix
        results = self._loop.run_until_complete(self._extract_batch(texts))

        batch["graph_nodes"] = [json.dumps(nodes) for nodes, _ in results]
        batch["graph_edges"] = [json.dumps(edges) for _, edges in results]
        return batch

    async def _extract_batch(self, texts: List[str]) -> List[Tuple[list, list]]:
        numbered = "\n\n".join(f"[Segment {i}]\n{text}" for i, text in enumerate(texts))
        try:
            content = await self._client.chat_completion(
                messages=[
                    {"role": "system", "content": GraphSchema.get_batch_system_prompt()},
                    {"role": "user", "content": numbered},
                ],
                temperature=0.0,
                json_mode=True,
            )
            segments = json.loads(content).get("segments", [])
            if len(segments) != len(texts):
                raise ValueError(
                    f"batch extraction returned {len(segments)} segments for {len(texts)} inputs"
                )
            return [(seg.get("nodes", []), seg.get("edges", [])) for seg in segments]

        except Exception as e:
            # Batch call failed to parse/align — fall back to one call per
            # chunk for THIS batch only, rather than silently dropping the
            # whole batch's graph data. If the backend is genuinely
            # exhausted (circuit open), these fail fast too, not slow.
            logger.warning(f"Batch graph extraction failed ({e}); falling back to per-chunk calls")
            results = []
            for text in texts:
                results.append(await self._extract_one(text))
            return results

    async def _extract_one(self, text: str) -> Tuple[list, list]:
        try:
            content = await self._client.chat_completion(
                messages=[
                    {"role": "system", "content": GraphSchema.get_system_prompt()},
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
                json_mode=True,
            )
            graph_data = json.loads(content)
            return graph_data.get("nodes", []), graph_data.get("edges", [])
        except Exception as e:
            logger.warning(f"Graph extraction failed for chunk: {e}")
            return [], []

    def __del__(self):
        # Best-effort cleanup when the actor is torn down — not critical
        # (the process is exiting anyway), just avoids a dangling
        # unclosed-client warning in logs.
        try:
            self._loop.run_until_complete(self._client.close())
            self._loop.close()
        except Exception:
            pass