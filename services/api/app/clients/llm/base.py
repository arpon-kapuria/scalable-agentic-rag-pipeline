"""
Common interface every LLM backend (Groq, OpenRouter, Ollama, vLLM) implements.
Callers (agent nodes, factory) depend on this, never on a concrete backend —
that's what makes LLM_BACKEND a config swap instead of a code change.
"""

from abc import ABC, abstractmethod
from typing import Dict, List


class LLMClient(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Called once during app startup (see main.py lifespan)."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Called once during app shutdown."""
        ...

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> str:
        """
        Returns the assistant's text response.
        Callers order `messages` with stable content (system prompt, tool
        schema) first and variable content (retrieved context, question)
        last — this earns Groq's automatic prompt caching for free and
        costs nothing on backends that don't support it.
        """
        ...
