from services.api.app.clients.llm.openai_compatible import OpenAICompatibleClient
from services.api.app.config import settings
from libs.utils.rate_limiter import BackendRateLimiter

# Per-model limits (free tier, as of this session — re-verify at
# console.groq.com/settings/limits if behavior seems off; these are NOT
# fetched dynamically, only used to seed the tracker before live headers
# arrive). Groq enforces RPM+RPD+TPM+TPD simultaneously per model —
# hitting ANY one trips a 429, and limits differ meaningfully by model
# (compound has no published token limit; the others share the same
# 8K TPM / 200K TPD envelope).
_GROQ_MODEL_LIMITS = {
    "groq/compound": dict(rpm=30, rpd=250),
    "openai/gpt-oss-120b": dict(rpm=30, rpd=1000, tpm=8000, tpd=200_000),
    "qwen/qwen3.8-27b": dict(rpm=30, rpd=1000, tpm=8000, tpd=200_000),
    "openai/gpt-oss-20b": dict(rpm=30, rpd=1000, tpm=8000, tpd=200_000),
}


def _build_groq_rate_limiter(models: list[str]) -> BackendRateLimiter:
    limiter = BackendRateLimiter(shared=False)
    for model in models:
        limits = _GROQ_MODEL_LIMITS.get(model)
        if limits:
            limiter.register(model, **limits)
        else:
            # Unknown model (list changed since _GROQ_MODEL_LIMITS was
            # last updated) — register with no limits rather than
            # blocking it outright; falls back to reactive 429 handling
            # for this one model only.
            limiter.register(model)
    return limiter


class GroqClient(OpenAICompatibleClient):
    """Groq's OpenAI-compatible endpoint. Prompt structure (stable content
    first, variable content last) earns Groq's automatic prompt caching —
    free, no code, 50% discount on cached prefix tokens — on every call."""

    def __init__(self):
        super().__init__(
            base_url="https://api.groq.com/openai/v1",
            models=settings.GROQ_MODELS,
            api_key=settings.GROQ_API_KEY,
            rate_limiter=_build_groq_rate_limiter(settings.GROQ_MODELS),
            header_style="groq",
        )
