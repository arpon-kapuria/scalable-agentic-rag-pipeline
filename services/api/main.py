from contextlib import asynccontextmanager
from fastapi import FastAPI
from services.api.app.clients.neo4j import neo4j_client
from services.api.app.clients.qdrant import qdrant_client
from services.api.app.clients.ray_llm import llm_client
from services.api.app.clients.ray_embed import embed_client
from services.api.app.cache.redis import redis_client
from services.api.app.memory.models import Base, ChatHistory, Feedback
from services.api.app.memory.postgres import engine
from services.api.app.routes import chat, upload, health, feedback

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Centralized Resource Management.
    Initialize all connection pools here.
    """

    # Create all tables defined in models.py
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 1. Startup
    print("Initializing clients...")
    await neo4j_client.connect()
    await redis_client.connect()
    await llm_client.start()
    await embed_client.start()

    await qdrant_client.init_collections()
    
    yield
    
    # 2. Shutdown
    print("Closing clients...")
    await neo4j_client.close()
    await redis_client.close()
    await llm_client.close()
    await embed_client.close()
    await qdrant_client.close()

# FastAPI Application
app = FastAPI(title="Enterprise RAG Platform", version="1.0.0", lifespan=lifespan)

# Include Routes
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])

if __name__ == "__main__":
    import uvicorn
    # In production, this is run via Gunicorn/Uvicorn in Docker
    uvicorn.run(app, host="0.0.0.0", port=8000)