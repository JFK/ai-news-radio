"""Anthropic (Claude) AI provider implementation."""

import base64

import anthropic

from app.config import settings
from app.services.ai_provider import AIProvider, AIResponse, ContentPart, SearchResult


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
        """Generate a response using Claude.

        Supports multimodal input via the `content` kwarg:
            content: list[ContentPart] — images are sent as base64.
        """
        content_parts: list[ContentPart] | None = kwargs.get("content")
        user_content = self._build_multimodal_content(prompt, content_parts) if content_parts else prompt

        params: dict = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "messages": [{"role": "user", "content": user_content}],
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

    @staticmethod
    def _build_multimodal_content(prompt: str, parts: list[ContentPart]) -> list[dict]:
        """Build Anthropic multimodal content blocks."""
        blocks: list[dict] = []
        for part in parts:
            if part.type == "text" and part.text:
                blocks.append({"type": "text", "text": part.text})
            elif part.type == "image" and part.data:
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": part.media_type or "image/png",
                            "data": base64.b64encode(part.data).decode(),
                        },
                    }
                )
            elif part.type == "pdf" and part.data:
                blocks.append(
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(part.data).decode(),
                        },
                    }
                )
        # Always add the text prompt at the end
        if prompt:
            blocks.append({"type": "text", "text": prompt})
        return blocks

    async def web_search(self, query: str, **kwargs) -> SearchResult:
        """Web search is not yet implemented for Anthropic."""
        raise NotImplementedError("Web search will be implemented in Phase 5")
