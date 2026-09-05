from services.api.app.clients.llm.openai_compatible import OpenAICompatibleClient
from services.api.app.config import settings
from libs.utils.rate_limiter import BackendRateLimiter

# Account-level, not per-model — OpenRouter's free-tier (:free models,
# unfunded account) cap is 20 requests/minute and 50 requests/day shared
# across every model, not per-model like Groq. Re-verify at
# openrouter.ai/docs/limits if you've since purchased $10+ in credits
# (raises the daily cap to 1000). No token dimension — OpenRouter's free
# limit is request-count only.
_OPENROUTER_RPM = 20
_OPENROUTER_RPD = 50


def _build_openrouter_rate_limiter() -> BackendRateLimiter:
    limiter = BackendRateLimiter(shared=True)
    limiter.register("_shared", rpm=_OPENROUTER_RPM, rpd=_OPENROUTER_RPD)
    return limiter


class OpenRouterClient(OpenAICompatibleClient):
    """OpenRouter's OpenAI-compatible endpoint. Automatic backup for Groq
    in the live demo (see factory.py) — never selected as primary unless
    API_PRIMARY=openrouter."""

    def __init__(self):
        super().__init__(
            base_url="https://openrouter.ai/api/v1",
            models=settings.OPENROUTER_MODELS,
            api_key=settings.OPENROUTER_API_KEY,
            rate_limiter=_build_openrouter_rate_limiter(),
            header_style="openrouter",
        )
