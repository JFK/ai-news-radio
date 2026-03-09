"""AI Provider abstraction layer.

Provides a unified interface for multiple AI providers (Anthropic, OpenAI, Google).
Each pipeline step can be configured to use a different provider/model via settings.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import settings


@dataclass
class AIResponse:
    """Response from an AI provider."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str


@dataclass
class SearchResult:
    """Result from a web search."""

    query: str
    results: list[dict] = field(default_factory=list)


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        **kwargs,
    ) -> AIResponse:
        """Generate a response from the AI model."""
        ...

    @abstractmethod
    async def web_search(self, query: str, **kwargs) -> SearchResult:
        """Perform a web search (provider-dependent)."""
        ...



# Step order for pipeline navigation
STEP_ORDER = ["collection", "factcheck", "analysis", "script", "voice", "video", "publish"]

# Mapping from step_name to config attribute prefix
_STEP_CONFIG_MAP = {
    "factcheck": "pipeline_factcheck",
    "analysis": "pipeline_analysis",
    "script": "pipeline_script",
}


def get_provider(provider_name: str) -> AIProvider:
    """Factory function to get an AI provider instance by name."""
    if provider_name == "anthropic":
        from app.services.providers.anthropic import AnthropicProvider

        return AnthropicProvider()
    elif provider_name == "openai":
        from app.services.providers.openai import OpenAIProvider

        return OpenAIProvider()
    elif provider_name == "google":
        from app.services.providers.google import GoogleProvider

        return GoogleProvider()
    else:
        raise ValueError(f"Unknown AI provider: {provider_name}")


def get_step_provider(step_name: str) -> tuple[AIProvider, str]:
    """Get the configured AI provider and model for a pipeline step.

    Returns:
        Tuple of (AIProvider instance, model name).
    """
    config_prefix = _STEP_CONFIG_MAP.get(step_name)
    if config_prefix:
        provider_name = getattr(settings, f"{config_prefix}_provider")
        model = getattr(settings, f"{config_prefix}_model")
    else:
        provider_name = settings.default_ai_provider
        model = settings.default_ai_model

    return get_provider(provider_name), model
