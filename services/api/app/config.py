import os
from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode
from typing import Annotated, List, Optional

class Settings(BaseSettings):
    """
    Application Configuration.
    Reads environment variables automatically (case-insensitive).
    """
    # General
    ENV: str = "prod"
    LOG_LEVEL: str = "INFO"
    
    # Database (Postgres)
    DATABASE_URL: str  # e.g., postgresql+asyncpg://user:pass@host:5432/db
    
    # Redis (Cache)
    REDIS_URL: str     # e.g., redis://elasticache-endpoint:6379/0
    
    # Vector DB (Qdrant)
    QDRANT_HOST: str = "qdrant-service"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "omnirag_collection"
    
    # Graph DB (Neo4j)
    NEO4J_URI: str = "bolt://neo4j-cluster:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str # Sensitive
    
    # AWS S3 (Documents)
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str
    
    # Ray Serve (Internal LLM/Embeddings) — frozen until Phase 11
    RAY_LLM_ENDPOINT: str = "http://llm-service:8000/llm"
    RAY_EMBEDDING_ENDPOINT: str = "http://embed-service:8000/embed"

    # --- LLM Backend Selection (Phase 1) ---
    # api = Groq/OpenRouter auto-failover pair (live demo default)
    # ollama | vllm_local | vllm_modal = manual-select only, never auto-triggered
    LLM_BACKEND: str = "api"
    # Only relevant when LLM_BACKEND=api. The other of the pair is automatic
    # backup on a retryable failure (429/5xx/timeout/connection).
    API_PRIMARY: str = "groq"

    # Groq (primary API backend)
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODELS: Annotated[List[str], NoDecode] = []

    # OpenRouter (backup API backend)
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODELS: Annotated[List[str], NoDecode] = []

    # Ollama (local Mac dev, offline, $0). One live test only — Phase 9.
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODELS: Annotated[List[str], NoDecode] = []

    # vLLM — manual-select only. Metal = local Mac; Modal = cloud GPU.
    VLLM_METAL_URL: str = "http://localhost:8001"
    VLLM_METAL_MODELS: Annotated[List[str], NoDecode] = []
    VLLM_MODAL_URL: Optional[str] = None
    VLLM_MODAL_API_KEY: Optional[str] = None
    VLLM_MODAL_MODELS: Annotated[List[str], NoDecode] = []

    @field_validator(
        "GROQ_MODELS", "OPENROUTER_MODELS", "OLLAMA_MODELS",
        "VLLM_METAL_MODELS", "VLLM_MODAL_MODELS",
        mode="before",
    )
    @classmethod
    def _split_priority_list(cls, v):
        """.env stores these as a single comma-separated, priority-sorted
        string (first = tried first); split into a list for the client code."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    # Security
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env" if os.path.exists(".env") else None
        extra = "ignore"

# Instantiate singleton
settings = Settings()