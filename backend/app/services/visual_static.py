"""Static visual provider — generates solid color backgrounds (no AI, free)."""

import asyncio
import logging

from app.services.visual_provider import VisualProvider

logger = logging.getLogger(__name__)

# Default dark background color
BG_COLOR = "#1a1a2e"


class StaticVisualProvider(VisualProvider):
    """Generates static solid-color images using FFmpeg. No external API needed."""

    async def generate_thumbnail(self, prompt: str, output_path: str) -> str:
        """Generate a solid color thumbnail (1280x720)."""
        return await self._generate_image(output_path, 1280, 720)

    async def generate_background_image(self, prompt: str, output_path: str) -> str:
        """Generate a solid color background (1920x1080)."""
        return await self._generate_image(output_path, 1920, 1080)

    async def generate_illustration(self, prompt: str, output_path: str) -> str:
        """Generate a solid color illustration placeholder (720x720)."""
        return await self._generate_image(output_path, 720, 720)

    async def health_check(self) -> bool:
        """Static provider is always available."""
        return True

    async def _generate_image(self, output_path: str, width: int, height: int) -> str:
        """Generate a solid color image using FFmpeg."""
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={BG_COLOR}:s={width}x{height}:d=1",
            "-frames:v", "1",
            output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg image generation failed: {stderr.decode()}")

        logger.info("Static image generated: %s (%dx%d)", output_path, width, height)
        return output_path
