from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from services.api.app.config import settings
from services.api.app.memory.models import ChatHistory

# Async Engine & Session
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

class PostgresMemory:
    """
    Manager for persisting conversation state.
    """
    async def add_message(self, corpus_id: str, role: str, content: str):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                msg = ChatHistory(
                    corpus_id=corpus_id,
                    role=role,
                    content=content,
                )
                session.add(msg)
                # Commit happens automatically via 'async with session.begin()'

    async def get_history(self, corpus_id: str, limit: int = 10):
        """
        Fetch last N messages for context window.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ChatHistory)
                .where(ChatHistory.corpus_id == corpus_id)
                .order_by(ChatHistory.created_at.desc())
                .limit(limit)
            )
            # Reverse to get chronological order (Oldest -> Newest)
            return result.scalars().all()[::-1]

postgres_memory = PostgresMemory()