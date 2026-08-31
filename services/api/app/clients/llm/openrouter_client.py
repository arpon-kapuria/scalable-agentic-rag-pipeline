from services.api.app.clients.llm.openai_compatible import OpenAICompatibleClient
from services.api.app.config import settings


class OpenRouterClient(OpenAICompatibleClient):
    """OpenRouter's OpenAI-compatible endpoint. Automatic backup for Groq
    in the live demo (see factory.py) — never selected as primary unless
    API_PRIMARY=openrouter."""

    def __init__(self):
        super().__init__(
            base_url="https://openrouter.ai/api/v1",
            models=settings.OPENROUTER_MODELS,
            api_key=settings.OPENROUTER_API_KEY,
        )
