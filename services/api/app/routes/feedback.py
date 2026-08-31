from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from services.api.app.memory.postgres import AsyncSessionLocal
from services.api.app.session.dependency import get_corpus_id

router = APIRouter()

class FeedbackRequest(BaseModel):
    message_id: int # ID of the assistant message from chat_history
    score: int # 1 (Like) or -1 (Dislike)
    comment: str | None = None

@router.post("/")
async def submit_feedback(
    req: FeedbackRequest,
    corpus_id: str = Depends(get_corpus_id)
):
    """
    Submit user feedback for an AI response.
    """
    try:
        async with AsyncSessionLocal() as session:
            # We create a simple feedback table or add a column to chat_history.
            # Here, let's assume a 'feedback' table exists (simple raw SQL for demo)
            await session.execute(
                text("""
                INSERT INTO feedback (corpus_id, message_id, score, comment)
                VALUES (:cid, :mid, :score, :comment)
                """),
                {
                    "cid": corpus_id,
                    "mid": req.message_id,
                    "score": req.score,
                    "comment": req.comment
                }
            )
            await session.commit()
            return {"status": "recorded"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))