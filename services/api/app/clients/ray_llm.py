"""
This file provides a reusable client that:
- Creates an async HTTP client with connection pooling.
- Sends chat requests from the API to the Ray-Serve LLM endpoint.
- Uses retry with exponential backoff for transient failures.
- Manages startup and shutdown of the connection pool.
- Returns the generated LLM response text.

Client
   ↓
FastAPI
   ↓
RayLLMClient
   ↓
Ray Serve LLM service (vLLM)
"""

import httpx
import logging

from typing import List, Dict, Optional
from services.api.app.config import settings
from libs.utils.backoff import exponential_backoff

logger = logging.getLogger(__name__)

class RayLLMClient:
    """
    Async Client with proper Connection Pooling.
    """
    def __init__(self):
        self.endpoint = settings.RAY_LLM_ENDPOINT
        # Client is initialized in startup_event
        self.client: Optional[httpx.AsyncClient] = None

    async def start(self):
        """Called during App Startup"""
        # Limits: prevent opening too many connections to Ray
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        self.client = httpx.AsyncClient(limits=limits, timeout=120.0)

        logger.info("Ray LLM Client initialized.")

    async def close(self):
        """Called during App Shutdown"""
        if self.client:
            await self.client.aclose()
            logger.info("Ray LLM Client closed.")

    @exponential_backoff(max_retries=3)
    async def chat_completion(self, messages: List[Dict], temperature: float=0.7, json_mode: bool=False):
        if not self.client:
            raise RuntimeError("Client not initialized. Call start() first.")
        
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = await self.client.post(self.endpoint, json=payload)
        response.raise_for_status()
        
        try:
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM PARSE ERROR: {e}")
            logger.error(f"RAW RESPONSE: {response.text}")
            raise

# Global Instance (Managed by Lifespan in main.py)
llm_client = RayLLMClient()