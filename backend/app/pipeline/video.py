"""Step 6: Video generation pipeline step."""

import asyncio
import json
import logging
import os

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import Episode, PipelineStep, StepName
from app.pipeline.base import BaseStep

logger = logging.getLogger(__name__)

# Font path for Japanese text rendering (Noto Sans CJK)
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


class VideoStep(BaseStep):
    """Generate video from audio and script text using FFmpeg."""

    @property
    def step_name(self) -> StepName:
        return StepName.VIDEO

    async def execute(self, episode_id: int, input_data: dict) -> dict:
        """Generate an MP4 video with scrolling script text over dark background.

        Reads audio_path from VoiceStep output, script text from DB,
        generates video with FFmpeg drawtext, saves to media/{episode_id}/video.mp4.
        """
        audio_path = input_data.get("audio_path", "")
        if not audio_path:
            raise ValueError("No audio_path in input data")

        audio_full_path = os.path.join(settings.media_dir, audio_path)
        if not os.path.exists(audio_full_path):
            raise ValueError(f"Audio file not found: {audio_full_path}")

        # Get script text from the script pipeline step
        script_text = await self._get_script_text(episode_id)

        # Get audio duration
        duration_seconds = await self._get_duration(audio_full_path)

        # Generate video
        episode_dir = os.path.join(settings.media_dir, str(episode_id))
        os.makedirs(episode_dir, exist_ok=True)
        video_path = os.path.join(episode_dir, "video.mp4")

        await self._generate_video(
            audio_path=audio_full_path,
            video_path=video_path,
            script_text=script_text,
            duration_seconds=duration_seconds,
        )

        # Update episode record
        relative_path = f"{episode_id}/video.mp4"
        async with async_session() as session:
            result = await session.execute(select(Episode).where(Episode.id == episode_id))
            episode = result.scalar_one()
            episode.video_path = relative_path
            await session.commit()

        logger.info("Episode %d: video saved to %s (%.1fs)", episode_id, relative_path, duration_seconds)

        return {
            "video_path": relative_path,
            "duration_seconds": duration_seconds,
        }

    async def _get_script_text(self, episode_id: int) -> str:
        """Get the episode script text from the script pipeline step."""
        async with async_session() as session:
            result = await session.execute(
                select(PipelineStep).where(
                    PipelineStep.episode_id == episode_id,
                    PipelineStep.step_name == StepName.SCRIPT,
                )
            )
            step = result.scalar_one()
            if step.output_data and "episode_script" in step.output_data:
                return step.output_data["episode_script"]
            return ""

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
        script_text: str,
        duration_seconds: float,
    ) -> None:
        """Generate MP4 video with scrolling text overlay using FFmpeg."""
        # Escape special characters for FFmpeg drawtext
        escaped_text = self._escape_drawtext(script_text)

        # Calculate scroll speed: text should scroll through during the audio duration
        # Text starts below the screen and scrolls up
        fontsize = 36
        line_height = fontsize + 10
        lines = escaped_text.count("\\n") + 1
        text_height = lines * line_height
        total_scroll = 1080 + text_height  # screen height + text height
        scroll_speed = total_scroll / duration_seconds if duration_seconds > 0 else 1

        # FFmpeg command: dark background + audio + scrolling text
        filter_complex = (
            f"color=c=#1a1a2e:s=1920x1080:d={duration_seconds}[bg];"
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
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a",
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
        # FFmpeg drawtext requires escaping: ' : \ and newlines
        text = text.replace("\\", "\\\\")
        text = text.replace("'", "'\\''")
        text = text.replace(":", "\\:")
        text = text.replace("\n", "\\n")
        return text
