from services.api.app.clients.llm.openai_compatible import OpenAICompatibleClient
from services.api.app.config import settings


class GroqClient(OpenAICompatibleClient):
    """Groq's OpenAI-compatible endpoint. Prompt structure (stable content
    first, variable content last) earns Groq's automatic prompt caching —
    free, no code, 50% discount on cached prefix tokens — on every call."""

    def __init__(self):
        super().__init__(
            base_url="https://api.groq.com/openai/v1",
            models=settings.GROQ_MODELS,
            api_key=settings.GROQ_API_KEY,
        )
