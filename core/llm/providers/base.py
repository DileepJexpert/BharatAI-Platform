"""Abstract base class for all LLM providers."""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Base interface that every LLM provider must implement."""

    provider_name: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Send chat completion request and return the text response."""

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the provider is reachable and functional."""

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return the list of models available for this provider."""

    async def close(self) -> None:
        """Cleanup any open connections."""
