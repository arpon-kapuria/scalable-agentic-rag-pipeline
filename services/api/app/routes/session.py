from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from services.api.app.config import settings
from services.api.app.session.dependency import SESSION_COOKIE_NAME
from services.api.app.session.store import session_store

router = APIRouter()


class SessionResponse(BaseModel):
    corpus_id: str
    created: bool


def _set_cookie(response: Response, corpus_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=corpus_id,
        httponly=True,
        samesite="lax",
        secure=settings.ENV == "prod",
        max_age=settings.SESSION_TTL_MINUTES * 60,
    )


@router.post("/init", response_model=SessionResponse)
async def init_session(request: Request, response: Response):
    """Issues a corpus_id (= session_id) as an httpOnly cookie on first
    visit. If a valid session cookie is already present, refreshes its
    TTL and returns the existing corpus_id instead of minting a new one —
    reloading the page shouldn't orphan the caller's corpus."""
    existing = request.cookies.get(SESSION_COOKIE_NAME)

    if existing and await session_store.is_valid(existing, settings.SESSION_TTL_MINUTES):
        await session_store.touch(existing)
        _set_cookie(response, existing)
        return SessionResponse(corpus_id=existing, created=False)

    corpus_id = await session_store.create_session()
    _set_cookie(response, corpus_id)
    return SessionResponse(corpus_id=corpus_id, created=True)