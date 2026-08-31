from fastapi import HTTPException, Request, status

from services.api.app.config import settings
from services.api.app.session.store import session_store

SESSION_COOKIE_NAME = "corpus_id"


async def get_corpus_id(request: Request) -> str:
    """Derives corpus_id server-side from the httpOnly session cookie.
    Never accepts a client-supplied corpus_id on data-touching routes —
    the cookie, set only by POST /session/init, is the single source."""
    corpus_id = request.cookies.get(SESSION_COOKIE_NAME)

    if not corpus_id or not await session_store.is_valid(corpus_id, settings.SESSION_TTL_MINUTES):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active session. Call POST /api/v1/session/init first.",
        )

    # Sliding window: any authenticated activity extends the session.
    await session_store.touch(corpus_id)
    return corpus_id