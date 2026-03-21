"""Image analysis service using multimodal AI.

Downloads images from URLs and analyzes them using AI vision models
to extract text descriptions of charts, infographics, photos, etc.
"""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.ai_provider import ContentPart, get_provider

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20MB
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}

IMAGE_ANALYSIS_PROMPT = """\
この画像を詳しく分析してください。以下の観点で記述してください:

1. 画像の種類（写真、チャート、インフォグラフィック、図表など）
2. 主な内容の説明
3. テキストが含まれている場合はその内容
4. 数値やデータが含まれている場合はその値
5. ニュース記事の文脈で重要な情報

日本語で回答してください。"""


@dataclass
class ImageAnalysisResult:
    """Result of image analysis."""

    description: str
    success: bool
    error: str | None = None


class ImageAnalyzerService:
    """Download and analyze images using AI vision models."""

    @staticmethod
    def is_image_url(url: str) -> bool:
        """Detect if URL points to an image based on extension."""
        lower = url.lower().split("?")[0]
        return any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS)

    async def analyze(
        self,
        url: str,
        provider_name: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> ImageAnalysisResult:
        """Download an image and analyze it with AI vision.

        Args:
            url: URL of the image.
            provider_name: AI provider to use (defaults to settings).
            model: AI model to use (defaults to settings).
            timeout: Download timeout in seconds.

        Returns:
            ImageAnalysisResult with text description or error.
        """
        try:
            image_data, media_type = await self._download_image(url, timeout)
        except Exception as e:
            return ImageAnalysisResult(description="", success=False, error=str(e))

        try:
            prov_name = provider_name or settings.collection_image_analysis_provider or settings.default_ai_provider
            mdl = model or settings.collection_image_analysis_model or settings.default_ai_model
            provider = get_provider(prov_name)

            response = await provider.generate(
                prompt=IMAGE_ANALYSIS_PROMPT,
                model=mdl,
                content=[ContentPart(type="image", data=image_data, media_type=media_type)],
            )
            return ImageAnalysisResult(description=response.content, success=True)
        except Exception as e:
            logger.warning("Image analysis failed for %s: %s", url, e)
            return ImageAnalysisResult(description="", success=False, error=str(e))

    async def _download_image(self, url: str, timeout: float) -> tuple[bytes, str]:
        """Download image with size limit. Returns (data, media_type)."""
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AINewsRadio/1.0)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        if len(response.content) > MAX_IMAGE_SIZE:
            raise ValueError(f"Image too large: {len(response.content)} bytes (max {MAX_IMAGE_SIZE})")

        content_type = response.headers.get("content-type", "image/png")
        # Normalize content type
        if "jpeg" in content_type or "jpg" in content_type:
            media_type = "image/jpeg"
        elif "png" in content_type:
            media_type = "image/png"
        elif "gif" in content_type:
            media_type = "image/gif"
        elif "webp" in content_type:
            media_type = "image/webp"
        else:
            media_type = "image/png"  # fallback

        return response.content, media_type
