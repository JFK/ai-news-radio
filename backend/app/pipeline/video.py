"""Step 6: Video generation pipeline step."""

import asyncio
import json
import logging
import os
import re
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

# Font paths for Japanese text rendering (Noto Sans CJK)
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_PATH_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

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
        await self.log_progress(episode_id, "[1/5] 背景画像を生成中...")
        try:
            await visual_provider.generate_background_image(bg_prompt, bg_image_path)
            images_generated += 1
        except Exception as e:
            logger.warning("Background image generation failed, using static fallback: %s", e)
            from app.services.visual_static import StaticVisualProvider
            await StaticVisualProvider().generate_background_image(bg_prompt, bg_image_path)

        await self.log_progress(episode_id, "[2/5] サムネイル画像を生成中...")
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

        # Apply the same title+border design to the video background
        video_bg_path = os.path.join(episode_dir, "video_background.png")
        self._overlay_title_on_thumbnail(bg_image_path, episode.title, output_path=video_bg_path)
        await self.log_progress(episode_id, "[2.5/5] 動画背景にタイトルオーバーレイ適用")

        # Get news items (needed for SRT and metadata)
        news_items = await self._get_news_items(episode_id, session)

        # Generate SRT subtitles from voice sections + script text
        srt_path = os.path.join(episode_dir, "subtitles.srt")
        voice_sections = input_data.get("sections", [])
        self._generate_srt(script_output, voice_sections, srt_path, news_items)
        await self.log_progress(episode_id, "[3/5] 字幕SRTを生成しました")

        await self.log_progress(episode_id, "[4/5] FFmpegで動画エンコード中...")
        video_task = self._generate_video(
            audio_path=audio_full_path,
            video_path=video_path,
            bg_image_path=video_bg_path,
            srt_path=srt_path,
        )
        # Pass timestamps from voice step if available
        timestamps = input_data.get("timestamps", "")

        await self.log_progress(episode_id, "[4/5] YouTubeメタデータを同時生成中...")
        metadata_task = self._generate_youtube_metadata(
            episode=episode,
            news_items=news_items,
            script_text=script_text,
            duration_seconds=duration_seconds,
            timestamps=timestamps,
            session=session,
        )

        _, youtube_metadata = await asyncio.gather(video_task, metadata_task)
        await self.log_progress(episode_id, "[5/5] 動画生成完了")

        # Update episode record
        relative_path = f"{episode_id}/video.mp4"
        episode.video_path = relative_path
        await session.commit()

        logger.info("Episode %d: video saved to %s (%.1fs)", episode_id, relative_path, duration_seconds)

        srt_relative = f"{episode_id}/subtitles.srt"
        result = {
            "video_path": relative_path,
            "srt_path": srt_relative,
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
        srt_path: str | None = None,
    ) -> None:
        """Generate MP4 video: background image + audio + optional SRT subtitles."""
        # Build filter: scale background, then optionally burn in subtitles
        if srt_path and os.path.exists(srt_path):
            # Escape path for FFmpeg filter (colons, backslashes)
            escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            filter_complex = (
                f"[0:v]loop=loop=-1:size=1:start=0,"
                f"setpts=N/FRAME_RATE/TB,scale=1280:720,setsar=1,"
                f"subtitles='{escaped_srt}'"
                f":force_style='FontName=Noto Sans CJK JP"
                f",FontSize=22,PrimaryColour=&H00FFFFFF"
                f",OutlineColour=&H00000000,BorderStyle=3"
                f",Outline=2,Shadow=1,BackColour=&H80000000"
                f",MarginV=30'"
                f"[v]"
            )
        else:
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

    def _generate_srt(
        self,
        script_output: dict,
        voice_sections: list[dict],
        srt_path: str,
        news_items: list[NewsItem],
    ) -> None:
        """Generate SRT subtitle file from script text and voice section timings.

        Splits each section's text into sentences, distributes duration
        proportionally by character count.
        """
        # Build section key → text mapping from script output
        section_texts: dict[str, str] = {}

        # Opening / ending from script output
        opening = script_output.get("opening", "")
        if opening:
            section_texts["opening"] = opening
        ending = script_output.get("ending", "")
        if ending:
            section_texts["ending"] = ending

        # CTA text
        if settings.youtube_cta_enabled and settings.youtube_cta_text:
            section_texts["cta"] = settings.youtube_cta_text

        # Outro text
        if settings.youtube_outro_enabled and settings.youtube_outro_text:
            section_texts["outro"] = settings.youtube_outro_text

        # Per-article scripts from NewsItem.script_text (DB)
        for item in news_items:
            if item.script_text:
                section_texts[f"news_{item.id}"] = item.script_text

        # Transitions
        transitions = script_output.get("transitions", [])
        for i, t in enumerate(transitions):
            if t:
                section_texts[f"transition_{i}"] = t

        # Build SRT entries
        # First pass: compute raw timings using reported durations + silence gap
        silence_gap = settings.voice_section_silence
        raw_entries: list[tuple[float, float, str]] = []
        elapsed = 0.0

        for sec in voice_sections:
            key = sec.get("key", "")
            duration = sec.get("duration_seconds", 0.0)
            text = section_texts.get(key, "")

            if text and duration > 0:
                # Remove reading hints like （けんぐん） or (けんぐん) from display text
                display = re.sub(r'[（\(][ぁ-んー]+[）\)]', '', text)

                # Split into sentences by Japanese period, question mark, etc.
                sentences = re.split(r'(?<=[。？！\?!])', display)
                sentences = [s.strip() for s in sentences if s.strip()]

                if not sentences:
                    sentences = [text]

                # Distribute duration proportionally by character count
                total_chars = sum(len(s) for s in sentences)
                if total_chars == 0:
                    total_chars = 1

                sub_elapsed = elapsed
                for sentence in sentences:
                    ratio = len(sentence) / total_chars
                    sub_duration = duration * ratio
                    # Limit subtitle length for readability
                    display_text = sentence
                    if len(display_text) > 40:
                        # Wrap long lines
                        mid = len(display_text) // 2
                        # Find a natural break point near the middle
                        for sep in ["、", "。", "（", "が", "の", "を", "に", "は", "で", "と"]:
                            pos = display_text.find(sep, mid - 10, mid + 10)
                            if pos > 0:
                                mid = pos + 1
                                break
                        display_text = display_text[:mid] + "\n" + display_text[mid:]

                    raw_entries.append((sub_elapsed, sub_elapsed + sub_duration, display_text))
                    sub_elapsed += sub_duration

            elapsed += duration + silence_gap

        # Apply fixed offset to all SRT timestamps (positive = subtitles appear later)
        offset = settings.srt_offset
        if offset:
            entries = [(max(0.0, s + offset), e + offset, t) for s, e, t in raw_entries]
        else:
            entries = raw_entries

        # Write SRT file
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, (start, end, text) in enumerate(entries, 1):
                f.write(f"{i}\n")
                f.write(f"{self._format_srt_time(start)} --> {self._format_srt_time(end)}\n")
                f.write(f"{text}\n\n")

        logger.info("SRT generated: %s (%d entries)", srt_path, len(entries))

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _overlay_title_on_thumbnail(self, image_path: str, title: str, output_path: str | None = None) -> None:
        """Overlay episode title on thumbnail with breaking-news style design.

        Design:
        - Background image darkened to serve as backdrop
        - Thick red border frame with padding
        - "AI NEWS RADIO" badge at top-left
        - Title text large and bold, centered in the middle
        - Semi-transparent highlight behind text for readability

        Args:
            image_path: Source image to overlay on.
            title: Episode title text.
            output_path: Where to save result. Defaults to image_path (overwrite).
        """
        if output_path is None:
            output_path = image_path
        img = Image.open(image_path).convert("RGBA")
        w, h = img.size

        # --- Darken the background image ---
        dark = Image.new("RGBA", (w, h), (0, 0, 0, 140))
        img = Image.alpha_composite(img, dark)

        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        # --- Parse border color from settings ---
        border_hex = settings.video_border_color or "#DC1E1E"
        try:
            border_hex = border_hex.lstrip("#")
            border_r = int(border_hex[0:2], 16)
            border_g = int(border_hex[2:4], 16)
            border_b = int(border_hex[4:6], 16)
        except (ValueError, IndexError):
            border_r, border_g, border_b = 220, 30, 30
        border_color = (border_r, border_g, border_b, 255)
        border_color_fill = (border_r, border_g, border_b, 240)

        # --- Thick border frame with padding ---
        border_width = int(min(w, h) * 0.05)  # ~5%
        draw_overlay.rectangle(
            [(0, 0), (w - 1, h - 1)],
            outline=border_color, width=border_width,
        )
        inner = border_width + 3
        draw_overlay.rectangle(
            [(inner, inner), (w - 1 - inner, h - 1 - inner)],
            outline=(255, 255, 255, 180), width=2,
        )

        # --- Logo or "AI NEWS RADIO" badge — top-left ---
        badge_pad = border_width + 12
        logo_path = settings.video_logo_path
        if logo_path and os.path.exists(logo_path):
            # Use custom logo image
            try:
                logo = Image.open(logo_path).convert("RGBA")
                # Scale logo to fit badge area (height ~10% of image)
                logo_max_h = int(h * 0.10)
                ratio = logo_max_h / logo.height
                logo_w = int(logo.width * ratio)
                logo = logo.resize((logo_w, logo_max_h), Image.Resampling.LANCZOS)
                overlay.paste(logo, (badge_pad, badge_pad), logo)
            except Exception as e:
                logger.warning("Logo load failed, falling back to text badge: %s", e)
                self._draw_text_badge(draw_overlay, badge_pad, h, border_color_fill)
        else:
            self._draw_text_badge(draw_overlay, badge_pad, h, border_color_fill)

        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # --- Split title before date pattern (e.g. "2026年3月15日") ---
        date_match = re.search(r'\s*(\d{4}年\d{1,2}月\d{1,2}日)\s*$', title)
        if date_match:
            title_main = title[:date_match.start()].strip()
            title_date = date_match.group(1)
        else:
            title_main = title
            title_date = None

        # --- Title text: large, bold, centered ---
        # Max 9 characters per line to keep text readable at large size
        max_chars_per_line = 9
        content_w = w - (border_width + inner + 10) * 2
        max_width = int(content_w * 0.90)
        fontsize = int(h * 0.18)  # ~18% — 1.5x bigger
        min_fontsize = int(h * 0.06)

        wrapped = textwrap.fill(title_main, width=max_chars_per_line)
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.load_default()
        while fontsize >= min_fontsize:
            try:
                font = ImageFont.truetype(FONT_PATH_BOLD, fontsize)
            except OSError:
                break

            lines = wrapped.split("\n")
            fits = all(
                draw.textlength(line, font=font) <= max_width for line in lines
            )
            if fits:
                break
            fontsize -= 2
        else:
            try:
                font = ImageFont.truetype(FONT_PATH_BOLD, min_fontsize)
            except OSError:
                pass

        lines = wrapped.split("\n")
        line_height = fontsize + 18
        total_text_height = len(lines) * line_height

        # Date line (smaller font below title)
        date_height = 0
        date_font = font
        if title_date:
            date_fontsize = int(fontsize * 0.55)
            try:
                date_font = ImageFont.truetype(FONT_PATH_BOLD, date_fontsize)
            except OSError:
                date_font = font
            date_height = date_fontsize + 20

        total_block_height = total_text_height + date_height

        # Center vertically (slightly above center for visual balance)
        y_start = (h - total_block_height) // 2 - int(h * 0.02)

        # --- Semi-transparent highlight background behind text ---
        highlight_pad_x = int(w * 0.05)
        highlight_pad_y = int(h * 0.035)
        highlight_overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        highlight_draw = ImageDraw.Draw(highlight_overlay)
        highlight_draw.rounded_rectangle(
            [
                (w // 2 - max_width // 2 - highlight_pad_x, y_start - highlight_pad_y),
                (w // 2 + max_width // 2 + highlight_pad_x, y_start + total_block_height + highlight_pad_y),
            ],
            radius=16,
            fill=(0, 0, 0, 160),
        )
        img = Image.alpha_composite(img, highlight_overlay)
        draw = ImageDraw.Draw(img)

        # --- Draw title text (bold, white, centered) ---
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (w - text_w) // 2
            y = y_start + i * line_height

            draw.text((x, y), line, font=font, fill="white",
                       stroke_width=5, stroke_fill=(20, 20, 20))

        # --- Draw date below title ---
        if title_date:
            date_bbox = draw.textbbox((0, 0), title_date, font=date_font)
            date_tw = date_bbox[2] - date_bbox[0]
            date_x = (w - date_tw) // 2
            date_y = y_start + total_text_height + 8
            draw.text((date_x, date_y), title_date, font=date_font, fill=(255, 220, 100),
                       stroke_width=2, stroke_fill=(20, 20, 20))

        # Save as RGB
        img.convert("RGB").save(output_path)
        logger.info("News-style title overlay applied: %s", output_path)

    @staticmethod
    def _draw_text_badge(
        draw: ImageDraw.ImageDraw,
        pad: int,
        img_h: int,
        bg_color: tuple[int, int, int, int],
    ) -> None:
        """Draw 'AI NEWS RADIO' text badge at top-left."""
        badge_fontsize = int(img_h * 0.07)
        try:
            badge_font = ImageFont.truetype(FONT_PATH_BOLD, badge_fontsize)
        except OSError:
            badge_font = ImageFont.load_default()
        badge_text = "AI NEWS RADIO"
        badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        badge_tw = badge_bbox[2] - badge_bbox[0]
        badge_th = badge_bbox[3] - badge_bbox[1]
        badge_rect_h = badge_th + int(img_h * 0.02)
        draw.rectangle(
            [(pad, pad), (pad + badge_tw + 24, pad + badge_rect_h)],
            fill=bg_color,
        )
        draw.text(
            (pad + 12, pad + int(img_h * 0.008)),
            badge_text, font=badge_font, fill="white",
        )
