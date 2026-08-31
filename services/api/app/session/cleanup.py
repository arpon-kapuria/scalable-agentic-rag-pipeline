import asyncio
import logging

from services.api.app.config import settings
from services.api.app.session.store import session_store

logger = logging.getLogger(__name__)

# Run twice per TTL window (floor 1 min) so a session is never more than
# ~ttl/2 stale before it's purged, without polling so often it's wasted work.
_CHECK_INTERVAL_SECONDS = max(60, (settings.SESSION_TTL_MINUTES * 60) // 2)


async def _cleanup_loop() -> None:
    while True:
        try:
            purged = await session_store.purge_expired(settings.SESSION_TTL_MINUTES)
            if purged:
                logger.info(f"Purged {len(purged)} expired session(s): {purged}")
                # Phase 3+ hook: once Qdrant/Neo4j/MinIO data is tagged with
                # corpus_id, cascade-delete it here using `purged`.
        except Exception as e:
            # Never let a transient Redis blip kill the loop.
            logger.error(f"Session cleanup pass failed: {e}", exc_info=True)

        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)


def start_cleanup_task() -> asyncio.Task:
    return asyncio.create_task(_cleanup_loop())


async def stop_cleanup_task(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass