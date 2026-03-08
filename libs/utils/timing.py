"""
Measures the execution time of various functions in our RAG pipeline for performance monitoring and optimization.
Handles both sync and async functions.
"""

import functools
import time
import inspect
import logging

logger = logging.getLogger("performance")

def measure_time(func):
    """
    Decorator to log execution time of asynchronous and synchronous functions.
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
        logger.info(f"{func.__name__} took {execution_time:.2f} ms")
        return result

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
        logger.info(f"{func.__name__} took {execution_time:.2f} ms")
        return result

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper