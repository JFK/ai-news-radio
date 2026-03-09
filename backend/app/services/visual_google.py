"""Google AI visual provider — Imagen 4 for image generation."""

import logging

from google import genai
from google.genai import types

from app.config import settings
from app.services.visual_provider import VisualProvider

logger = logging.getLogger(__name__)


class GoogleVisualProvider(VisualProvider):
    """Generates images using Google Imagen 4 via the Gemini API."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.google_api_key)

    async def generate_thumbnail(self, prompt: str, output_path: str) -> str:
        """Generate a thumbnail image (16:9) using Imagen 4."""
        return await self._generate_image(
            prompt=f"News thumbnail image: {prompt}. Clean, professional, photorealistic style.",
            output_path=output_path,
            aspect_ratio="16:9",
        )

    async def generate_background_image(self, prompt: str, output_path: str) -> str:
        """Generate a background image (16:9) using Imagen 4."""
        return await self._generate_image(
            prompt=f"Dark, subtle background image for news video: {prompt}. Muted colors, low contrast, suitable for text overlay.",
            output_path=output_path,
            aspect_ratio="16:9",
        )

    async def health_check(self) -> bool:
        """Check if Google API is accessible."""
        try:
            return bool(settings.google_api_key)
        except Exception:
            return False

    async def _generate_image(self, prompt: str, output_path: str, aspect_ratio: str = "16:9") -> str:
        """Generate an image using Imagen 4."""
        logger.info("Generating image with Imagen 4: %s", prompt[:80])

        response = self._client.models.generate_images(
            model=settings.visual_imagen_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
            ),
        )

        if not response.generated_images:
            raise RuntimeError("Imagen 4 returned no images")

        image = response.generated_images[0].image
        image.save(output_path)

        logger.info("Image saved: %s", output_path)
        return output_path
