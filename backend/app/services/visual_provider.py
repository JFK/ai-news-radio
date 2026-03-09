"""Abstract base class for visual content providers (thumbnails, background video)."""

from abc import ABC, abstractmethod

from app.config import settings


class VisualProvider(ABC):
    """Generates visual assets for video production."""

    @abstractmethod
    async def generate_thumbnail(self, prompt: str, output_path: str) -> str:
        """Generate a thumbnail image from a text prompt.

        Args:
            prompt: Description of the desired image.
            output_path: Path to save the generated image (PNG).

        Returns:
            Path to the saved image file.
        """
        ...

    @abstractmethod
    async def generate_background_image(self, prompt: str, output_path: str) -> str:
        """Generate a background image for the video.

        Args:
            prompt: Description of the desired background.
            output_path: Path to save the generated image (PNG).

        Returns:
            Path to the saved image file.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        ...


def get_visual_provider() -> VisualProvider:
    """Get the configured visual provider instance."""
    provider = settings.visual_provider

    if provider == "google":
        from app.services.visual_google import GoogleVisualProvider
        return GoogleVisualProvider()
    elif provider == "static":
        from app.services.visual_static import StaticVisualProvider
        return StaticVisualProvider()
    else:
        raise ValueError(f"Unknown visual provider: {provider}")
