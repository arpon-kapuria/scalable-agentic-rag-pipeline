import redis.asyncio as redis
from services.api.app.config import settings

class RedisClient:
    """
    Singleton Redis connection pool.
    Used for Rate Limiting and Semantic Cache storage.
    """
    def __init__(self):
        self.redis = None

    async def connect(self):
        if not self.redis:
            # decode_responses=True means we get Strings back, not Bytes
            self.redis = redis.from_url(
                settings.REDIS_URL, 
                encoding="utf-8", 
                decode_responses=True
            )

    async def close(self):
        if self.redis:
            await self.redis.close()

    def get_client(self):
        if self.redis is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self.redis

# Global instance
redis_client = RedisClient()