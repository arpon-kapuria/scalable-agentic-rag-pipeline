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
from libs.utils.circuit_breaker import CircuitBreaker, CircuitOpenError
from libs.utils.rate_limiter import BackendRateLimiter, estimate_tokens

logger = logging.getLogger(__name__)


class ModelExhaustedError(Exception):
    """Every model in this backend's priority list failed (or was already
    known rate-limited). Signals the factory's failover wrapper (if any)
    to try the backup backend."""


class OpenAICompatibleClient(LLMClient):
    """
    Tries `models` in priority order per call. Before attempting a model
    at all, checks its rate-limit budget (libs/utils/rate_limiter.py) —
    if that model is already known to be exhausted (locally tracked,
    corrected by live provider headers when available), it's SKIPPED with
    no HTTP call whatsoever, not attempted-then-caught. This is the actual
    efficiency win on free-tier limits: a skipped call costs nothing,
    whereas even a failed attempt burns quota on some providers
    (OpenRouter's daily cap counts failed attempts the same as successful
    ones).

    Each model that IS attempted gets exponential_backoff's own retries
    first; only a fully-exhausted model (still failing after backoff)
    causes a move to the next model in the list. If every model is either
    rate-limited or fails, raises ModelExhaustedError.

    A circuit breaker sits in front of the whole backend: once
    CIRCUIT_FAILURE_THRESHOLD consecutive ModelExhaustedErrors happen
    (every model failed, repeatedly), further calls fail fast for a
    cooldown window instead of re-attempting every model's full retry
    sequence again.
    """

    def __init__(
        self,
        base_url: str,
        models: List[str],
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        rate_limiter: Optional[BackendRateLimiter] = None,
        header_style: str = "none",  # "groq" | "openrouter" | "none"
    ):
        self.base_url = base_url.rstrip("/")
        self.models = models
        self.api_key = api_key
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None
        self._circuit = CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0)
        self._rate_limiter = rate_limiter
        self._header_style = header_style

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

        # Fail fast if this backend has been exhausted repeatedly and is
        # still cooling down — skips straight to ModelExhaustedError
        # without burning another full model-list retry sequence.
        try:
            self._circuit.before_call()
        except CircuitOpenError as e:
            raise ModelExhaustedError(str(e)) from e

        estimated_tokens = estimate_tokens(messages)
        last_error: Optional[Exception] = None
        any_attempted = False

        for model in self.models:
            tracker = self._rate_limiter.get(model) if self._rate_limiter else None

            # Proactive skip — no HTTP call at all if we already know this
            # model's budget is exhausted. This is the real efficiency
            # win: a skipped call costs nothing; an attempted-then-failed
            # one can cost real quota (OpenRouter counts failed attempts
            # against the daily cap).
            if tracker is not None and not tracker.can_proceed(estimated_tokens):
                logger.info(f"{self.__class__.__name__}: skipping '{model}' — locally tracked as rate-limited.")
                continue

            any_attempted = True
            if tracker is not None:
                tracker.record_attempt(estimated_tokens)

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
                self._record_headers(tracker, response.headers)
                content = response.json()["choices"][0]["message"]["content"]

                # Bug 1 fix: an HTTP 200 with empty/blank content (observed
                # from groq/compound under load) was previously treated as
                # success — silently returned, no retry, no failover. That
                # produced ~15% silent data loss in GraphExtractor (empty
                # string handed to json.loads() -> "Expecting value" error,
                # swallowed by its own soft-fail). Empty output is a
                # failure like any other here now.
                if not content or not content.strip():
                    raise ValueError(f"model '{model}' returned empty content")

                self._circuit.record_success()
                return content
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                last_error = e
                if isinstance(e, httpx.HTTPStatusError):
                    self._record_headers(tracker, e.response.headers)
                logger.warning(f"{self.__class__.__name__}: model '{model}' failed ({e}); trying next.")
                continue
            except (KeyError, IndexError, ValueError) as e:
                last_error = e
                logger.error(f"{self.__class__.__name__}: bad response from '{model}': {e}")
                continue

        self._circuit.record_failure()
        if not any_attempted:
            logger.warning(f"{self.__class__.__name__}: all {len(self.models)} model(s) skipped — rate-limited, no calls made.")
        raise ModelExhaustedError(
            f"{self.__class__.__name__}: all {len(self.models)} model(s) exhausted"
        ) from last_error

    def _record_headers(self, tracker, headers) -> None:
        if tracker is None:
            return
        if self._header_style == "groq":
            tracker.record_groq_headers(headers)
        elif self._header_style == "openrouter":
            tracker.record_openrouter_headers(headers)

    @exponential_backoff(max_retries=2)
    async def _post_with_retry(self, payload: dict) -> httpx.Response:
        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        return response
