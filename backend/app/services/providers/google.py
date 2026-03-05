"""Google (Gemini) AI provider implementation."""

import google.generativeai as genai

from app.config import settings
from app.services.ai_provider import AIProvider, AIResponse, SearchResult


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
        """Generate a response using Gemini."""
        gen_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system,
        )

        response = await gen_model.generate_content_async(prompt)

        # Extract token counts from usage_metadata
        usage = response.usage_metadata
        return AIResponse(
            content=response.text or "",
            input_tokens=usage.prompt_token_count if usage else 0,
            output_tokens=usage.candidates_token_count if usage else 0,
            model=model,
            provider="google",
        )

    async def web_search(self, query: str, **kwargs) -> SearchResult:
        """Web search is not yet implemented for Google."""
        raise NotImplementedError("Web search will be implemented in Phase 5")
