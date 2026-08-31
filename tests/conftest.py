import os

# config.py's Settings() instantiates at import time and requires these.
# Set them before any `services.api.app.*` import happens, so tests don't
# need a real .env file or live infra.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("NEO4J_PASSWORD", "test")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GROQ_MODELS", "model-a,model-b")
os.environ.setdefault("OPENROUTER_API_KEY", "test-or-key")
os.environ.setdefault("OPENROUTER_MODELS", "or-model-a,or-model-b")
