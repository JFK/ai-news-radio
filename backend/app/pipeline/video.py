"""Step 6: Video generation pipeline step."""

import asyncio
import json
import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Episode, PipelineStep, StepName
from app.pipeline.base import BaseStep
from app.services.visual_provider import get_visual_provider

logger = logging.getLogger(__name__)

# Font path for Japanese text rendering (Noto Sans CJK)
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


class VideoStep(BaseStep):
    """Generate video from audio, background image, and script text."""

    @property
    def step_name(self) -> StepName:
        return StepName.VIDEO

    async def execute(self, episode_id: int, input_data: dict, session: AsyncSession, **kwargs) -> dict:
        """Generate an MP4 video with scrolling script text over background image.

        1. Generate background image (AI or static)
        2. Generate thumbnail image
        3. Compose video with FFmpeg: background + audio + scrolling text
        """
        audio_path = input_data.get("audio_path", "")
        if not audio_path:
            raise ValueError("No audio_path in input data")

        audio_full_path = os.path.join(settings.media_dir, audio_path)
        if not os.path.exists(audio_full_path):
            raise ValueError(f"Audio file not found: {audio_full_path}")

        # Get script step output (text + image prompts)
        script_output = await self._get_script_step_output(episode_id, session)
        script_text = script_output.get("episode_script", "")

        # Get audio duration
        duration_seconds = await self._get_duration(audio_full_path)

        # Setup output paths
        episode_dir = os.path.join(settings.media_dir, str(episode_id))
        os.makedirs(episode_dir, exist_ok=True)
        video_path = os.path.join(episode_dir, "video.mp4")
        bg_image_path = os.path.join(episode_dir, "background.png")
        thumbnail_path = os.path.join(episode_dir, "thumbnail.png")

        # Get episode title as fallback prompt
        ep_result = await session.execute(select(Episode).where(Episode.id == episode_id))
        episode = ep_result.scalar_one()

        # Use AI-generated prompts from scriptwriter, fallback to episode title
        visual_provider = get_visual_provider()
        bg_prompt = script_output.get("background_prompt") or episode.title
        thumb_prompt = script_output.get("thumbnail_prompt") or episode.title

        try:
            await visual_provider.generate_background_image(bg_prompt, bg_image_path)
        except Exception as e:
            logger.warning("Background image generation failed, using static fallback: %s", e)
            from app.services.visual_static import StaticVisualProvider
            await StaticVisualProvider().generate_background_image(bg_prompt, bg_image_path)

        try:
            await visual_provider.generate_thumbnail(thumb_prompt, thumbnail_path)
            thumbnail_relative = f"{episode_id}/thumbnail.png"
        except Exception as e:
            logger.warning("Thumbnail generation failed: %s", e)
            thumbnail_relative = None

        # Compose video
        await self._generate_video(
            audio_path=audio_full_path,
            video_path=video_path,
            bg_image_path=bg_image_path,
            script_text=script_text,
            duration_seconds=duration_seconds,
        )

        # Update episode record
        relative_path = f"{episode_id}/video.mp4"
        episode.video_path = relative_path
        await session.commit()

        logger.info("Episode %d: video saved to %s (%.1fs)", episode_id, relative_path, duration_seconds)

        result = {
            "video_path": relative_path,
            "duration_seconds": duration_seconds,
            "visual_provider": settings.visual_provider,
        }
        if thumbnail_relative:
            result["thumbnail_path"] = thumbnail_relative

        return result

    async def _get_script_step_output(self, episode_id: int, session: AsyncSession) -> dict:
        """Get the script pipeline step's output_data."""
        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode_id,
                PipelineStep.step_name == StepName.SCRIPT,
            )
        )
        step = result.scalar_one()
        return step.output_data or {}

    async def _get_duration(self, audio_path: str) -> float:
        """Get audio duration using ffprobe."""
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json",
            audio_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {stderr.decode()}")

        data = json.loads(stdout.decode())
        return float(data["format"]["duration"])

    async def _generate_video(
        self,
        audio_path: str,
        video_path: str,
        bg_image_path: str,
        script_text: str,
        duration_seconds: float,
    ) -> None:
        """Generate MP4 video with scrolling text overlay using FFmpeg."""
        escaped_text = self._escape_drawtext(script_text)

        fontsize = 36
        line_height = fontsize + 10
        lines = escaped_text.count("\\n") + 1
        text_height = lines * line_height
        total_scroll = 1080 + text_height
        scroll_speed = total_scroll / duration_seconds if duration_seconds > 0 else 1

        # FFmpeg: background image (looped) + audio + scrolling text
        filter_complex = (
            f"[0:v]loop=loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB,scale=1920:1080,setsar=1[bg];"
            f"[bg]drawtext="
            f"fontfile={FONT_PATH}:"
            f"text='{escaped_text}':"
            f"fontcolor=white:"
            f"fontsize={fontsize}:"
            f"x=(w-text_w)/2:"
            f"y=h-{scroll_speed}*t:"
            f"line_spacing=10"
            f"[v]"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", bg_image_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            video_path,
        ]

        logger.debug("FFmpeg command: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed (exit {proc.returncode}): {stderr.decode()}")

        logger.info("FFmpeg completed: %s", video_path)

    def _escape_drawtext(self, text: str) -> str:
        """Escape text for FFmpeg drawtext filter."""
        text = text.replace("\\", "\\\\")
        text = text.replace("'", "'\\''")
        text = text.replace(":", "\\:")
        text = text.replace("\n", "\\n")
        return text
