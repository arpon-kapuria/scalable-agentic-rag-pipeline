"""
We use a formula `base * (2 ^ retries) + random_jitter` to calculate the delay before each retry. This helps us to prevent the Thundering Herd problem where multiple clients retry at the same time.
"""

import logging
import functools
import random
import asyncio
import httpx

logger = logging.getLogger(__name__)

def exponential_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
    """
    Decorator for Exponential Backoff with Jitter.
    Retries async functions upon exception.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except httpx.HTTPError as e:
                    if retries >= max_retries:
                        logger.error(f"Max retries reached for {func.__name__}: {e}")
                        raise e
                    
                    # Algorithm: base * (2 ^ retries) + random_jitter
                    # Jitter prevents "Thundering Herd" problem on the server
                    delay = min(base_delay * (2 ** retries), max_delay)
                    jitter = random.uniform(0, 0.5)
                    sleep_time = delay + jitter

                    logger.warning(f"Error in {func.__name__}: {e}. Retrying in {sleep_time:.2f}s...")
                    await asyncio.sleep(sleep_time)
                    retries += 1
        return wrapper
    return decorator
