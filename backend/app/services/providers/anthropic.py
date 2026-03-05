"""Anthropic (Claude) AI provider implementation."""

import anthropic

from app.config import settings
from app.services.ai_provider import AIProvider, AIResponse, SearchResult


class AnthropicProvider(AIProvider):
    """AI provider using Anthropic's Claude API."""

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        **kwargs,
    ) -> AIResponse:
        """Generate a response using Claude."""
        params: dict = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            params["system"] = system

        response = await self._client.messages.create(**params)

        return AIResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=model,
            provider="anthropic",
        )

    async def web_search(self, query: str, **kwargs) -> SearchResult:
        """Web search is not yet implemented for Anthropic."""
        raise NotImplementedError("Web search will be implemented in Phase 5")
