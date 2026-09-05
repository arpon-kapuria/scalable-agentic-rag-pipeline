"""
Circuit breaker: after N consecutive failures, a backend is marked "open"
and calls fail fast (no network round-trip) for a cooldown window, instead
of every caller independently retrying into the same 429 wall. Half-open
after cooldown: one trial call decides whether to close (reset) or reopen.

Used per-backend (one instance per GroqClient/OpenRouterClient etc, not
shared globally) — a Groq outage shouldn't fail-fast OpenRouter calls too.
"""
import time
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"      # normal operation
    OPEN = "open"           # failing fast, cooling down
    HALF_OPEN = "half_open"  # cooldown elapsed, next call is a trial


class CircuitOpenError(Exception):
    """Raised instead of making a call while the circuit is open."""


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._state = CircuitState.CLOSED

    def _current_state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def before_call(self):
        """Call before attempting the request. Raises CircuitOpenError if
        the circuit is open and cooldown hasn't elapsed."""
        if self._current_state() == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit open ({self._consecutive_failures} consecutive failures) — "
                f"cooling down for {self.cooldown_seconds}s before retrying"
            )

    def record_success(self):
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None

    def record_failure(self):
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
