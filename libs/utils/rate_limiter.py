"""
Proactive client-side rate limiting — checked BEFORE attempting a call,
not discovered via a 429 after the fact. Two real, different provider
behaviors drove this design, confirmed via each provider's docs:

Groq: returns live x-ratelimit-* headers on EVERY response (success or
429) — x-ratelimit-remaining-requests, -tokens, -reset-requests,
-reset-tokens. Limits are enforced PER MODEL (RPM+RPD+TPM+TPD
simultaneously). Static known limits below seed the tracker; real
headers correct it as soon as any call is made, becoming the source of
truth over the static estimate.

OpenRouter: successful responses carry NO rate-limit headers at all —
only error responses do (X-RateLimit-Limit/-Remaining/-Reset, request-
count only, no token dimension). Worse: failed/429 attempts still
consume the daily quota, same as a successful call. There is no live
signal on the (common) success path, so this is local-count-only there —
the entire value is refusing to attempt a call we can already predict
will fail, since a failed attempt costs exactly as much as a successful
one. Limit is ACCOUNT-LEVEL (shared across every model), not per-model.

Static limits are current as of this session (told directly by the
person running this project) — Groq/OpenRouter free-tier limits shift
over time; re-verify against console.groq.com/settings/limits and
openrouter.ai/docs/limits if behavior seems off.
"""
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class _Window:
    """Tracks usage within one rolling time window (e.g. 'requests per minute')."""
    limit: Optional[int]
    period_seconds: float
    count: int = 0
    window_start: float = field(default_factory=time.monotonic)
    # Live, provider-reported values (Groq always; OpenRouter on error
    # only) — None until a real header arrives, then preferred over the
    # local estimate until it expires.
    live_remaining: Optional[int] = None
    live_reset_at: Optional[float] = None

    def _maybe_roll(self):
        now = time.monotonic()
        if now - self.window_start >= self.period_seconds:
            self.window_start = now
            self.count = 0

    def remaining(self) -> Optional[int]:
        if self.limit is None:
            return None  # no cap tracked for this window/metric
        now = time.monotonic()
        if self.live_remaining is not None and self.live_reset_at and now < self.live_reset_at:
            return self.live_remaining
        self._maybe_roll()
        return max(0, self.limit - self.count)

    def record_attempt(self, amount: int = 1):
        self._maybe_roll()
        self.count += amount
        if self.live_remaining is not None:
            self.live_remaining = max(0, self.live_remaining - amount)

    def record_live(self, remaining: int, reset_in_seconds: float):
        self.live_remaining = remaining
        self.live_reset_at = time.monotonic() + max(reset_in_seconds, 0.0)


class ModelRateLimiter:
    """One of these per (backend, model) for Groq-style per-model limits,
    or one shared instance for OpenRouter-style account-level limits."""

    def __init__(
        self,
        rpm: Optional[int] = None,
        rpd: Optional[int] = None,
        tpm: Optional[int] = None,
        tpd: Optional[int] = None,
    ):
        self.requests_minute = _Window(rpm, 60) if rpm else None
        self.requests_day = _Window(rpd, 86400) if rpd else None
        self.tokens_minute = _Window(tpm, 60) if tpm else None
        self.tokens_day = _Window(tpd, 86400) if tpd else None

    def can_proceed(self, estimated_tokens: int = 0) -> bool:
        for window in (self.requests_minute, self.requests_day):
            if window is not None:
                remaining = window.remaining()
                if remaining is not None and remaining <= 0:
                    return False
        for window in (self.tokens_minute, self.tokens_day):
            if window is not None:
                remaining = window.remaining()
                if remaining is not None and remaining < estimated_tokens:
                    return False
        return True

    def record_attempt(self, estimated_tokens: int = 0):
        for window in (self.requests_minute, self.requests_day):
            if window is not None:
                window.record_attempt(1)
        for window in (self.tokens_minute, self.tokens_day):
            if window is not None:
                window.record_attempt(estimated_tokens)

    def record_groq_headers(self, headers) -> None:
        """Groq's requests/tokens headers don't self-identify which
        window (RPM vs RPD, TPM vs TPD) they represent — community
        reports say "requests" commonly maps to RPD and "tokens" to TPM,
        but this varies by account/tier. Applied to whichever window is
        actually configured for this model, preferring the daily/minute
        window that exists."""
        try:
            if "x-ratelimit-remaining-requests" in headers:
                remaining = int(headers["x-ratelimit-remaining-requests"])
                reset_s = _parse_groq_reset(headers.get("x-ratelimit-reset-requests", "60s"))
                target = self.requests_day or self.requests_minute
                if target:
                    target.record_live(remaining, reset_s)
            if "x-ratelimit-remaining-tokens" in headers:
                remaining = int(headers["x-ratelimit-remaining-tokens"])
                reset_s = _parse_groq_reset(headers.get("x-ratelimit-reset-tokens", "60s"))
                target = self.tokens_minute or self.tokens_day
                if target:
                    target.record_live(remaining, reset_s)
        except (ValueError, TypeError):
            pass  # malformed header — keep the local estimate, don't crash the call

    def record_openrouter_headers(self, headers) -> None:
        """Only present on OpenRouter error responses, request-count only."""
        try:
            if "x-ratelimit-remaining" in headers:
                remaining = int(headers["x-ratelimit-remaining"])
                reset_s = _parse_openrouter_reset(headers.get("x-ratelimit-reset"))
                target = self.requests_day or self.requests_minute
                if target:
                    target.record_live(remaining, reset_s)
        except (ValueError, TypeError):
            pass


def _parse_groq_reset(value: str) -> float:
    """Groq reset format: '1.2s', '120ms', '2m59.56s', '6m0s'."""
    value = value.strip()
    try:
        if value.endswith("ms"):
            return float(value[:-2]) / 1000
        if "m" in value and value.endswith("s"):
            minutes, seconds = value.split("m")
            return float(minutes) * 60 + float(seconds.rstrip("s"))
        if value.endswith("s"):
            return float(value[:-1])
        return float(value)
    except ValueError:
        return 60.0


def _parse_openrouter_reset(value) -> float:
    """OpenRouter's X-RateLimit-Reset is a Unix timestamp (ms), per docs."""
    if not value:
        return 60.0
    try:
        reset_at_ms = float(value)
        return max(0.0, reset_at_ms / 1000 - time.time())
    except (ValueError, TypeError):
        return 60.0


class BackendRateLimiter:
    """
    Owns per-model trackers (Groq: limits differ per model) or one shared
    tracker (OpenRouter: one account-level pool regardless of model).
    """

    def __init__(self, shared: bool = False):
        self._shared = shared
        self._trackers: dict[str, ModelRateLimiter] = {}
        self._shared_tracker: Optional[ModelRateLimiter] = None

    def register(self, model: str, **limits):
        tracker = ModelRateLimiter(**limits)
        if self._shared:
            self._shared_tracker = tracker
        else:
            self._trackers[model] = tracker

    def get(self, model: str) -> Optional[ModelRateLimiter]:
        if self._shared:
            return self._shared_tracker
        return self._trackers.get(model)


def estimate_tokens(messages: list[dict]) -> int:
    """Rough ~4 chars/token heuristic — not exact, just enough to avoid
    obviously blowing a TPM/TPD budget. A real tokenizer would be more
    accurate but adds a dependency for a proactive-only estimate that
    gets corrected by live headers on the next call anyway."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return max(1, total_chars // 4)
