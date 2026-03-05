"""OpenAI AI provider implementation."""

import openai

from app.config import settings
from app.services.ai_provider import AIProvider, AIResponse, SearchResult


class OpenAIProvider(AIProvider):
    """AI provider using OpenAI's API."""

    def __init__(self) -> None:
        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        **kwargs,
    ) -> AIResponse:
        """Generate a response using OpenAI."""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 4096),
        )

        usage = response.usage
        return AIResponse(
            content=response.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=model,
            provider="openai",
        )

    async def web_search(self, query: str, **kwargs) -> SearchResult:
        """Web search is not yet implemented for OpenAI."""
        raise NotImplementedError("Web search will be implemented in Phase 5")
