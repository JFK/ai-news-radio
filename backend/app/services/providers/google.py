"""Google (Gemini) AI provider implementation."""

import google.generativeai as genai

from app.config import settings
from app.services.ai_provider import AIProvider, AIResponse, ContentPart, SearchResult


class GoogleProvider(AIProvider):
    """AI provider using Google's Gemini API."""

    def __init__(self) -> None:
        genai.configure(api_key=settings.google_api_key)

    async def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        **kwargs,
    ) -> AIResponse:
        """Generate a response using Gemini.

        Supports multimodal input via the `content` kwarg:
            content: list[ContentPart] — images/PDFs sent as inline data.
            Gemini natively supports PDF input.
        """
        gen_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system,
        )

        content_parts: list[ContentPart] | None = kwargs.get("content")
        gen_content = self._build_multimodal_content(prompt, content_parts) if content_parts else prompt

        response = await gen_model.generate_content_async(gen_content)

        # Extract token counts from usage_metadata
        usage = response.usage_metadata
        return AIResponse(
            content=response.text or "",
            input_tokens=usage.prompt_token_count if usage else 0,
            output_tokens=usage.candidates_token_count if usage else 0,
            model=model,
            provider="google",
        )

    @staticmethod
    def _build_multimodal_content(prompt: str, parts: list[ContentPart]) -> list:
        """Build Gemini multimodal content parts."""
        content: list = []
        for part in parts:
            if part.type == "text" and part.text:
                content.append(part.text)
            elif part.type == "image" and part.data:
                content.append(
                    {
                        "mime_type": part.media_type or "image/png",
                        "data": part.data,
                    }
                )
            elif part.type == "pdf" and part.data:
                content.append(
                    {
                        "mime_type": "application/pdf",
                        "data": part.data,
                    }
                )
        # Add prompt text at the end
        if prompt:
            content.append(prompt)
        return content

    async def web_search(self, query: str, **kwargs) -> SearchResult:
        """Web search is not yet implemented for Google."""
        raise NotImplementedError("Web search will be implemented in Phase 5")
