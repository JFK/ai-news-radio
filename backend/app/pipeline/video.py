"""Step 6: Video generation pipeline step."""

import asyncio
import json
import logging
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Episode, NewsItem, PipelineStep, StepName
from app.pipeline.base import BaseStep
from app.pipeline.utils import parse_json_response
from app.services.ai_provider import get_step_provider
from app.services.prompt_loader import get_active_prompt, register_default
from app.services.visual_provider import get_visual_provider

logger = logging.getLogger(__name__)

# Font path for Japanese text rendering (Noto Sans CJK)
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

PROMPT_KEY = "youtube_metadata"

YOUTUBE_METADATA_SYSTEM_PROMPT = """\
あなたはYouTubeのSEO・アルゴリズム最適化の専門家です。
ニュースラジオ番組の動画に最適なメタデータを生成してください。

## ルール

### title（60文字以内）
- 検索されやすいキーワードを自然に含める
- クリックベイトにならない範囲で興味を引く
- 【】で主要トピックを冒頭に

### description（日本語、2000文字以内）
- 冒頭3行で要点（折りたたみ前に表示される部分が重要）
- ⏱ タイムスタンプ（0:00 オープニング、おおよそのセクション位置）
- 📌 ニュース一覧
- 関連キーワードを自然に含める
- 末尾にクレジット: 📻 AI News Radio Japan

### tags（配列、合計500文字以内）
- ニュース関連キーワード
- 地域名・トピック固有のタグ
- 日本語と英語を混ぜる
- 15-25個程度

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "title": "動画タイトル",
  "description": "概要文",
  "tags": ["タグ1", "タグ2", ...]
}"""

register_default(PROMPT_KEY, YOUTUBE_METADATA_SYSTEM_PROMPT)


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

        images_generated = 0
        await self.log_progress(episode_id, "[1/4] 背景画像を生成中...")
        try:
            await visual_provider.generate_background_image(bg_prompt, bg_image_path)
            images_generated += 1
        except Exception as e:
            logger.warning("Background image generation failed, using static fallback: %s", e)
            from app.services.visual_static import StaticVisualProvider
            await StaticVisualProvider().generate_background_image(bg_prompt, bg_image_path)

        await self.log_progress(episode_id, "[2/4] サムネイル画像を生成中...")
        try:
            await visual_provider.generate_thumbnail(thumb_prompt, thumbnail_path)
            self._overlay_title_on_thumbnail(thumbnail_path, episode.title)
            thumbnail_relative = f"{episode_id}/thumbnail.png"
            images_generated += 1
        except Exception as e:
            logger.warning("Thumbnail generation failed: %s", e)
            thumbnail_relative = None

        # Record Imagen cost if images were generated via Google
        if images_generated > 0 and settings.visual_provider == "google":
            await self.record_usage(
                session=session,
                episode_id=episode_id,
                provider="google-imagen",
                model=settings.visual_imagen_model,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.04 * images_generated,  # Imagen 4 Fast: ~$0.04/image
            )

        # Run FFmpeg encoding and YouTube metadata generation in parallel
        news_items = await self._get_news_items(episode_id, session)

        await self.log_progress(episode_id, "[3/4] FFmpegで動画エンコード中...")
        video_task = self._generate_video(
            audio_path=audio_full_path,
            video_path=video_path,
            bg_image_path=bg_image_path,
            script_text=script_text,
            duration_seconds=duration_seconds,
        )
        # Pass timestamps from voice step if available
        timestamps = input_data.get("timestamps", "")

        await self.log_progress(episode_id, "[3/4] YouTubeメタデータを同時生成中...")
        metadata_task = self._generate_youtube_metadata(
            episode=episode,
            news_items=news_items,
            script_text=script_text,
            duration_seconds=duration_seconds,
            timestamps=timestamps,
            session=session,
        )

        _, youtube_metadata = await asyncio.gather(video_task, metadata_task)
        await self.log_progress(episode_id, "[4/4] 動画生成完了")

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
        if youtube_metadata:
            result["youtube_metadata"] = youtube_metadata

        return result

    async def _generate_youtube_metadata(
        self,
        episode: Episode,
        news_items: list[NewsItem],
        script_text: str,
        duration_seconds: float,
        timestamps: str,
        session: AsyncSession,
    ) -> dict | None:
        """Generate YouTube metadata (title, description, tags) using AI."""
        try:
            provider, model = get_step_provider("script")  # Reuse script step's AI config
            system_prompt, _prompt_version = await get_active_prompt(session, PROMPT_KEY)

            news_summary = "\n".join(f"- {item.title}" for item in news_items)
            duration_min = int(duration_seconds // 60)
            duration_sec = int(duration_seconds % 60)

            timestamps_info = f"\n\nタイムスタンプ（正確な値）:\n{timestamps}" if timestamps else ""

            prompt = (
                f"番組タイトル: {episode.title}\n"
                f"ニュース一覧:\n{news_summary}\n"
                f"動画の長さ: {duration_min}分{duration_sec}秒\n\n"
                f"台本の冒頭300文字:\n{script_text[:300]}"
                f"{timestamps_info}"
            )

            response = await provider.generate(prompt=prompt, model=model, system=system_prompt)
            data = parse_json_response(response.content)

            await self.record_usage(
                session=session,
                episode_id=episode.id,
                provider=response.provider,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

            logger.info("Episode %d: YouTube metadata generated", episode.id)
            return {
                "title": data.get("title", ""),
                "description": data.get("description", ""),
                "tags": data.get("tags", []),
            }

        except Exception as e:
            logger.warning("YouTube metadata generation failed: %s", e)
            return None

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
        """Generate MP4 video: background image + audio (no text overlay)."""
        # FFmpeg: static background image (looped) + audio → 720p MP4
        filter_complex = (
            "[0:v]loop=loop=-1:size=1:start=0,"
            "setpts=N/FRAME_RATE/TB,scale=1280:720,setsar=1[v]"
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
            "-preset", "ultrafast",
            "-crf", "28",
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

    def _overlay_title_on_thumbnail(self, image_path: str, title: str) -> None:
        """Overlay episode title on thumbnail with news-style design.

        Design:
        - Red accent bar at top with "AI NEWS RADIO" badge
        - Dark gradient overlay on bottom half
        - Large bold white title text with thick black outline
        - Thin red/white border frame for polished look
        """
        img = Image.open(image_path).convert("RGBA")
        w, h = img.size

        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        # --- Top accent bar: red banner with channel name ---
        bar_height = int(h * 0.07)
        draw_overlay.rectangle([(0, 0), (w, bar_height)], fill=(220, 30, 30, 230))

        try:
            badge_font = ImageFont.truetype(FONT_PATH, int(bar_height * 0.55))
        except OSError:
            badge_font = ImageFont.load_default()
        badge_text = "AI NEWS RADIO"
        draw_overlay.text(
            (int(w * 0.03), int(bar_height * 0.18)),
            badge_text, font=badge_font, fill="white",
        )

        # --- Bottom gradient overlay (stronger, covering bottom 55%) ---
        gradient_top = int(h * 0.45)
        for y in range(gradient_top, h):
            progress = (y - gradient_top) / (h - gradient_top)
            alpha = int(230 * progress)
            draw_overlay.rectangle([(0, y), (w, y + 1)], fill=(0, 0, 0, alpha))

        # --- Border frame: thin red outer + white inner ---
        border = 4
        draw_overlay.rectangle([(0, 0), (w - 1, h - 1)], outline=(220, 30, 30, 255), width=border)
        draw_overlay.rectangle(
            [(border, border), (w - 1 - border, h - 1 - border)],
            outline=(255, 255, 255, 180), width=2,
        )

        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # --- Title text: auto-size, large and impactful ---
        max_width = int(w * 0.88)
        fontsize = int(h * 0.10)  # Start at ~10% of image height (bigger)
        min_fontsize = int(h * 0.05)

        wrapped = title
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.load_default()
        while fontsize >= min_fontsize:
            try:
                font = ImageFont.truetype(FONT_PATH, fontsize)
            except OSError:
                break

            wrapped = textwrap.fill(title, width=max(1, max_width // (fontsize // 2)))
            lines = wrapped.split("\n")
            fits = all(
                draw.textlength(line, font=font) <= max_width for line in lines
            )
            if fits and len(lines) <= 3:
                break
            fontsize -= 2
        else:
            try:
                font = ImageFont.truetype(FONT_PATH, min_fontsize)
            except OSError:
                pass
            wrapped = textwrap.fill(title, width=max(1, max_width // (min_fontsize // 2)))

        lines = wrapped.split("\n")
        line_height = fontsize + 12
        total_text_height = len(lines) * line_height

        # Position: bottom area, above border
        y_start = h - total_text_height - int(h * 0.06)

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (w - text_w) // 2
            y = y_start + i * line_height

            # Thick black outline + yellow shadow for impact
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 160),
                       stroke_width=5, stroke_fill="black")
            # Main white text with strong outline
            draw.text((x, y), line, font=font, fill="white",
                       stroke_width=4, stroke_fill=(30, 30, 30))

        # Save as RGB
        img.convert("RGB").save(image_path)
        logger.info("News-style title overlay applied to thumbnail: %s", image_path)
