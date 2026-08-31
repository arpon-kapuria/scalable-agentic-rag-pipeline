"""
Groq, OpenRouter, Ollama, and both vLLM variants all speak the OpenAI
/chat/completions schema, so one base class covers them all — thin
subclasses just supply base_url/models/api_key. Mirrors the raw-httpx
pattern already used by clients/ray_llm.py rather than adding an SDK dep.
"""

import httpx
import logging
from typing import Dict, List, Optional

from services.api.app.clients.llm.base import LLMClient
from libs.utils.backoff import exponential_backoff

logger = logging.getLogger(__name__)


class ModelExhaustedError(Exception):
    """Every model in this backend's priority list failed. Signals the
    factory's failover wrapper (if any) to try the backup backend."""


class OpenAICompatibleClient(LLMClient):
    """
    Tries `models` in priority order per call. Each model gets
    exponential_backoff's own retries first; only a fully-exhausted model
    (still failing after backoff) causes a move to the next model in the
    list. If every model fails, raises ModelExhaustedError.
    """

    def __init__(
        self,
        base_url: str,
        models: List[str],
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.models = models
        self.api_key = api_key
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None

    async def start(self):
        if not self.models:
            raise RuntimeError(
                f"{self.__class__.__name__}: no models configured "
                f"(check the corresponding *_MODELS var in .env)"
            )
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
        self.client = httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=self.timeout, limits=limits
        )
        logger.info(f"{self.__class__.__name__} initialized ({len(self.models)} model(s) configured).")

    async def close(self):
        if self.client:
            await self.client.aclose()
            logger.info(f"{self.__class__.__name__} closed.")

    async def chat_completion(
        self, messages: List[Dict], temperature: float = 0.3, json_mode: bool = False
    ) -> str:
        if not self.client:
            raise RuntimeError(f"{self.__class__.__name__} not started. Call start() first.")

        last_error: Optional[Exception] = None
        for model in self.models:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 1024,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            try:
                response = await self._post_with_retry(payload)
                return response.json()["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                last_error = e
                logger.warning(f"{self.__class__.__name__}: model '{model}' failed ({e}); trying next.")
                continue
            except (KeyError, IndexError, ValueError) as e:
                last_error = e
                logger.error(f"{self.__class__.__name__}: bad response shape from '{model}': {e}")
                continue

        raise ModelExhaustedError(
            f"{self.__class__.__name__}: all {len(self.models)} model(s) exhausted"
        ) from last_error

    @exponential_backoff(max_retries=2)
    async def _post_with_retry(self, payload: dict) -> httpx.Response:
        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        return response
