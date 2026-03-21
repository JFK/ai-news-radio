"""OpenAI AI provider implementation."""

import base64
import logging

import openai

from app.config import settings
from app.services.ai_provider import AIProvider, AIResponse, ContentPart, SearchResult

logger = logging.getLogger(__name__)


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
        """Generate a response using OpenAI.

        Supports multimodal input via the `content` kwarg:
            content: list[ContentPart] — images are sent as base64 data URLs.
        """
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})

        content_parts: list[ContentPart] | None = kwargs.get("content")
        if content_parts:
            user_content = self._build_multimodal_content(prompt, content_parts)
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=kwargs.get("max_tokens", 16384),
        )

        usage = response.usage
        return AIResponse(
            content=response.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=model,
            provider="openai",
        )

    @staticmethod
    def _build_multimodal_content(prompt: str, parts: list[ContentPart]) -> list[dict]:
        """Build OpenAI multimodal content blocks."""
        blocks: list[dict] = []
        for part in parts:
            if part.type == "text" and part.text:
                blocks.append({"type": "text", "text": part.text})
            elif part.type == "image" and part.data:
                media = part.media_type or "image/png"
                b64 = base64.b64encode(part.data).decode()
                blocks.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media};base64,{b64}"},
                    }
                )
            elif part.type == "pdf":
                logger.warning("OpenAI does not support native PDF input; PDF content will be skipped")
        # Add prompt text at the end
        if prompt:
            blocks.append({"type": "text", "text": prompt})
        return blocks

    async def web_search(self, query: str, **kwargs) -> SearchResult:
        """Web search is not yet implemented for OpenAI."""
        raise NotImplementedError("Web search will be implemented in Phase 5")
