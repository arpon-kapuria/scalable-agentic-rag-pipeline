from services.api.app.clients.llm.openai_compatible import OpenAICompatibleClient
from services.api.app.config import settings


class VLLMClient(OpenAICompatibleClient):
    """vLLM's OpenAI-compatible server. Manual-select only, never an
    auto-failover target — cold starts make live GPU inference too risky
    for a demo. Used to record one-time clips proving the real engine
    works, then the live path reverts to Groq/OpenRouter.

    variant="metal": local Mac (vllm-metal), small quantized model.
    variant="modal": Modal-hosted GPU, within Modal's $30/mo free credit.
    """

    def __init__(self, variant: str = "metal"):
        if variant == "metal":
            base_url = settings.VLLM_METAL_URL
            models = settings.VLLM_METAL_MODELS
            api_key = None
        elif variant == "modal":
            if not settings.VLLM_MODAL_URL:
                raise RuntimeError("VLLM_MODAL_URL is not set — required for LLM_BACKEND=vllm_modal")
            base_url = settings.VLLM_MODAL_URL
            models = settings.VLLM_MODAL_MODELS
            api_key = settings.VLLM_MODAL_API_KEY
        else:
            raise ValueError(f"Unknown vLLM variant: {variant!r} (expected 'metal' or 'modal')")

        super().__init__(base_url=base_url, models=models, api_key=api_key)
        self.variant = variant
