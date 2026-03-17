"""Step 6: Video generation pipeline step."""

import asyncio
import json
import logging
import os
import re
import textwrap
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Episode, NewsItem, PipelineStep, StepName
from app.models.speaker_profile import SpeakerProfile
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
SHORTS_PROMPT_KEY = "shorts_youtube_metadata"

SHORTS_YOUTUBE_METADATA_SYSTEM_PROMPT = """\
あなたはYouTube Shortsの最適化の専門家です。
ニュースショート動画に最適なメタデータを生成してください。

## ルール

### title（40文字以内）
- 短く、インパクトのある一言
- #Shorts に最適化（ハッシュタグは別途tagsに）

### description（200文字以内）
- 要点を簡潔に
- 本編動画への誘導を含める

### hashtags（配列、5-8個）
- 関連するハッシュタグ
- #Shorts を必ず含める
- 日本語タグ中心

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "title": "ショートタイトル",
  "description": "短い説明文",
  "hashtags": ["#Shorts", "#ニュース", ...]
}"""

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
register_default(SHORTS_PROMPT_KEY, SHORTS_YOUTUBE_METADATA_SYSTEM_PROMPT)


@dataclass(frozen=True)
class FrameLayout:
    """Layout constants for frame composition (landscape or portrait)."""

    width: int
    height: int
    logo_y: int
    logo_centered: bool  # False=top-left, True=center
    illust_y: int
    illust_w: int
    illust_h: int
    illust_centered: bool  # True=horizontally centered, False=use illust_x
    illust_x: int  # used when illust_centered=False
    avatar_y: int
    avatar_explainer_size: int
    avatar_explainer_gap: int
    avatar_solo_size: int
    avatar_centered: bool  # True=horizontally centered, False=use avatar_base_x
    avatar_base_x: int  # used when avatar_centered=False
    name_fontsize: int
    topic_fontsize: int  # 0=hidden
    topic_y: int
    subtitle_fontsize: int  # 0=hidden
    subtitle_y: int
    subtitle_wrap_width: int
    dark_alpha: int  # background darkening alpha


LANDSCAPE = FrameLayout(
    width=1280, height=720,
    logo_y=12, logo_centered=False,
    illust_y=80, illust_w=460, illust_h=345, illust_centered=False, illust_x=80,
    avatar_y=140, avatar_explainer_size=180, avatar_explainer_gap=50,
    avatar_solo_size=220, avatar_centered=False, avatar_base_x=600,
    name_fontsize=16, topic_fontsize=24, topic_y=15,
    subtitle_fontsize=0, subtitle_y=0, subtitle_wrap_width=0,
    dark_alpha=120,
)

PORTRAIT = FrameLayout(
    width=1080, height=1920,
    logo_y=30, logo_centered=True,
    illust_y=150, illust_w=800, illust_h=400, illust_centered=True, illust_x=0,
    avatar_y=620, avatar_explainer_size=250, avatar_explainer_gap=60,
    avatar_solo_size=320, avatar_centered=True, avatar_base_x=0,
    name_fontsize=20, topic_fontsize=0, topic_y=0,
    subtitle_fontsize=38, subtitle_y=1300, subtitle_wrap_width=16,
    dark_alpha=140,
)


class VideoStep(BaseStep):
    """Generate video from audio, background image, and script text."""

    @property
    def step_name(self) -> StepName:
        return StepName.VIDEO

    # Valid targets for partial re-run
    VALID_TARGETS = frozenset({"all", "images", "video", "metadata", "shorts"})

    async def execute(self, episode_id: int, input_data: dict, session: AsyncSession, **kwargs) -> dict:
        """Generate an MP4 video with news-style layout.

        Pipeline:
        1. Generate background image (AI or static)
        2. Generate thumbnail image
        3. Generate illustration images per news article
        4. Compose segment frames (Pillow: bg + illustration + avatar + logo + topic)
        5. Generate SRT subtitles
        6. FFmpeg video encode (segment frames overlaid by time)
        7. YouTube metadata + Shorts generation

        Supports partial re-run via `targets` kwarg (list of target names).
        Valid targets: all, images, video, metadata, shorts.
        """
        # --- Parse targets ---
        targets = set(kwargs.get("targets", ["all"]))
        invalid = targets - self.VALID_TARGETS
        if invalid:
            raise ValueError(f"無効なターゲット: {invalid}。有効値: {', '.join(sorted(self.VALID_TARGETS))}")
        run_all = "all" in targets

        # Partial re-run: load existing output_data for merging
        existing_output: dict = {}
        if not run_all:
            step_result = await session.execute(
                select(PipelineStep).where(
                    PipelineStep.episode_id == episode_id,
                    PipelineStep.step_name == StepName.VIDEO,
                )
            )
            step_record = step_result.scalar_one()
            existing_output = step_record.output_data or {}
            if not existing_output:
                raise ValueError("初回はフル実行が必要です (targets=['all'])")
            await self.log_progress(
                episode_id,
                f"部分再実行: {', '.join(sorted(targets))}",
            )

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

        # Get news items (needed for illustrations, SRT, metadata, shorts)
        news_items = await self._get_news_items(episode_id, session)

        # Load speaker profiles for avatar overlays
        speakers_result = await session.execute(select(SpeakerProfile))
        speakers_by_role: dict[str, SpeakerProfile] = {}
        for sp in speakers_result.scalars():
            speakers_by_role[sp.role] = sp

        # --- Images target: stages 1-3 ---
        thumbnail_relative: str | None = None
        illustration_paths: dict[int, str] = {}

        if run_all or "images" in targets:
            visual_provider = get_visual_provider()
            bg_prompt = script_output.get("background_prompt") or episode.title
            thumb_prompt = script_output.get("thumbnail_prompt") or episode.title

            images_generated = 0
            await self.log_progress(episode_id, "[1/7] 背景画像を生成中...")
            try:
                await visual_provider.generate_background_image(bg_prompt, bg_image_path)
                images_generated += 1
            except Exception as e:
                logger.warning("Background image generation failed, using static fallback: %s", e)
                from app.services.visual_static import StaticVisualProvider
                await StaticVisualProvider().generate_background_image(bg_prompt, bg_image_path)

            await self.log_progress(episode_id, "[2/7] サムネイル画像を生成中...")
            try:
                await visual_provider.generate_thumbnail(thumb_prompt, thumbnail_path)
                self._overlay_title_on_thumbnail(thumbnail_path, episode.title)
                thumbnail_relative = f"{episode_id}/thumbnail.png"
                images_generated += 1
            except Exception as e:
                logger.warning("Thumbnail generation failed: %s", e)

            # [3/7] Generate illustration images per news article
            await self.log_progress(episode_id, "[3/7] 解説画像を生成中...")
            illustration_paths = await self._generate_illustrations(
                episode_id, news_items, visual_provider, episode_dir,
            )
            images_generated += len(illustration_paths)

            # Record Imagen cost if images were generated via Google
            if images_generated > 0 and settings.visual_provider == "google":
                await self.record_usage(
                    session=session,
                    episode_id=episode_id,
                    provider="google-imagen",
                    model=settings.visual_imagen_model,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.04 * images_generated,
                )
        else:
            # Discover existing illustrations from disk
            illustration_paths = self._discover_existing_illustrations(episode_dir, news_items)
            if os.path.exists(thumbnail_path):
                thumbnail_relative = f"{episode_id}/thumbnail.png"

        # --- Video target: stages 4-6 ---
        segment_frames: list[dict] = []
        if run_all or "video" in targets:
            if not os.path.exists(bg_image_path):
                raise ValueError("背景画像がありません。先に images を実行してください。")

            voice_sections = input_data.get("sections", [])

            # [4/7] Compose segment frames (Pillow)
            await self.log_progress(episode_id, "[4/7] セグメントフレームを合成中...")
            segment_frames = self._generate_segment_frames(
                episode_dir=episode_dir,
                bg_image_path=bg_image_path,
                news_items=news_items,
                voice_sections=voice_sections,
                speakers_by_role=speakers_by_role,
                illustration_paths=illustration_paths,
                episode_title=episode.title,
            )

            # [5/7] Generate SRT subtitles
            srt_path = os.path.join(episode_dir, "subtitles.srt")
            self._generate_srt(script_output, voice_sections, srt_path, news_items)
            await self.log_progress(episode_id, "[5/7] 字幕SRTを生成しました")

            # [6/7] FFmpeg video encode
            await self.log_progress(episode_id, "[6/7] FFmpegで動画エンコード中...")
            await self._ffmpeg_encode_video(
                audio_path=audio_full_path,
                video_path=video_path,
                base_image_path=bg_image_path,
                resolution=(1280, 720),
                segment_frames=segment_frames,
                srt_path=srt_path,
            )

            # Update episode record
            relative_path = f"{episode_id}/video.mp4"
            episode.video_path = relative_path
            await session.commit()

        # --- Metadata target: stage 7a ---
        youtube_metadata = None
        if run_all or "metadata" in targets:
            timestamps = input_data.get("timestamps", "")
            await self.log_progress(episode_id, "[7/7] YouTubeメタデータを生成中...")
            youtube_metadata = await self._generate_youtube_metadata(
                episode=episode,
                news_items=news_items,
                script_text=script_text,
                duration_seconds=duration_seconds,
                timestamps=timestamps,
                session=session,
                speakers_by_role=speakers_by_role,
            )

        # --- Shorts target: stage 7b ---
        shorts_results: list[dict] = []
        shorts_data = input_data.get("shorts", [])
        if shorts_data and (run_all or "shorts" in targets):
            if not os.path.exists(bg_image_path):
                raise ValueError("背景画像がありません。先に images を実行してください。")
            await self.log_progress(episode_id, "ショート動画を生成中...")
            shorts_results = await self._generate_shorts_videos(
                episode_id=episode_id,
                shorts_data=shorts_data,
                news_items=news_items,
                illustration_paths=illustration_paths,
                bg_image_path=bg_image_path,
                speakers_by_role=speakers_by_role,
                session=session,
                episode_dir=episode_dir,
            )
            await self.log_progress(episode_id, f"ショート動画 {len(shorts_results)}本 生成完了")

        await self.log_progress(episode_id, "動画生成完了")

        # --- Build result, merging with existing output for partial re-runs ---
        result: dict = {**existing_output}

        if run_all or "video" in targets:
            relative_path = f"{episode_id}/video.mp4"
            srt_relative = f"{episode_id}/subtitles.srt"
            result["video_path"] = relative_path
            result["srt_path"] = srt_relative
            result["duration_seconds"] = duration_seconds
            result["visual_provider"] = settings.visual_provider
            result["segment_count"] = len(segment_frames)

        if run_all or "images" in targets:
            result["visual_provider"] = settings.visual_provider
            if thumbnail_relative:
                result["thumbnail_path"] = thumbnail_relative
            if illustration_paths:
                result["illustration_paths"] = [
                    f"{episode_id}/illustrations/{os.path.basename(p)}"
                    for p in illustration_paths.values()
                ]

        if run_all or "metadata" in targets:
            if youtube_metadata:
                result["youtube_metadata"] = youtube_metadata

        if run_all or "shorts" in targets:
            if shorts_results:
                result["shorts"] = shorts_results

        # Ensure duration_seconds is always present
        if "duration_seconds" not in result:
            result["duration_seconds"] = duration_seconds

        logger.info("Episode %d: video step completed (targets=%s)", episode_id, targets)
        return result

    # ------------------------------------------------------------------
    # Illustration generation
    # ------------------------------------------------------------------

    async def _generate_illustrations(
        self,
        episode_id: int,
        news_items: list[NewsItem],
        visual_provider: object,
        episode_dir: str,
    ) -> dict[int, str]:
        """Generate illustration images for news items that have illustration_prompt.

        Returns:
            Mapping of news_item_id → absolute file path.
        """
        illust_dir = os.path.join(episode_dir, "illustrations")
        os.makedirs(illust_dir, exist_ok=True)

        items_with_prompt: list[tuple[NewsItem, str]] = []
        for item in news_items:
            if item.script_data and isinstance(item.script_data, dict):
                prompt = item.script_data.get("illustration_prompt", "")
                if prompt:
                    items_with_prompt.append((item, prompt))

        if not items_with_prompt:
            return {}

        sem = asyncio.Semaphore(3)
        results: dict[int, str] = {}

        async def _gen(item: NewsItem, prompt: str) -> None:
            output_path = os.path.join(illust_dir, f"news_{item.id}.png")
            async with sem:
                try:
                    await visual_provider.generate_illustration(prompt, output_path)  # type: ignore[attr-defined]
                    results[item.id] = output_path
                except Exception as e:
                    logger.warning(
                        "Illustration generation failed for item %d, using fallback: %s",
                        item.id, e,
                    )
                    try:
                        from app.services.visual_static import StaticVisualProvider
                        await StaticVisualProvider().generate_illustration(prompt, output_path)
                        results[item.id] = output_path
                    except Exception:
                        pass

        await asyncio.gather(*[_gen(item, prompt) for item, prompt in items_with_prompt])
        logger.info("Episode %d: generated %d/%d illustrations", episode_id, len(results), len(items_with_prompt))
        return results

    @staticmethod
    def _discover_existing_illustrations(
        episode_dir: str, news_items: list[NewsItem]
    ) -> dict[int, str]:
        """Discover existing illustration images on disk for partial re-runs."""
        illust_dir = os.path.join(episode_dir, "illustrations")
        if not os.path.isdir(illust_dir):
            return {}
        results: dict[int, str] = {}
        for item in news_items:
            path = os.path.join(illust_dir, f"news_{item.id}.png")
            if os.path.exists(path):
                results[item.id] = path
        return results

    # ------------------------------------------------------------------
    # Segment frame composition (Pillow)
    # ------------------------------------------------------------------

    def _generate_segment_frames(
        self,
        episode_dir: str,
        bg_image_path: str,
        news_items: list[NewsItem],
        voice_sections: list[dict],
        speakers_by_role: dict[str, "SpeakerProfile"],
        illustration_paths: dict[int, str],
        episode_title: str = "",
    ) -> list[dict]:
        """Generate composite segment frame images for each voice section.

        Returns a list of dicts: [{path, start_at, end_at}, ...] for news sections.
        Non-news sections (opening, transition, ending) use the base background.
        """
        frames_dir = os.path.join(episode_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)

        # Build news_item_id lookup
        items_by_id: dict[int, NewsItem] = {item.id: item for item in news_items}

        # Load background as base
        try:
            bg_img = Image.open(bg_image_path).convert("RGBA")
            bg_img = bg_img.resize((1280, 720), Image.Resampling.LANCZOS)
        except Exception:
            bg_img = Image.new("RGBA", (1280, 720), (26, 26, 46, 255))

        # Load logo
        logo_img = self._load_logo()

        # Preload avatar images
        avatars = self._load_avatars(speakers_by_role)

        segment_frames: list[dict] = []
        frame_idx = 0

        for sec in voice_sections:
            key = sec.get("key", "")
            start_at = sec.get("start_at", 0.0)
            end_at = sec.get("end_at", start_at + sec.get("duration_seconds", 0.0))
            news_item_id = sec.get("news_item_id")

            # Non-news sections (opening, transition, ending, cta, outro):
            # Show title card with logo + avatar
            if not key.startswith("news_") or news_item_id is None:
                frame_path = os.path.join(frames_dir, f"seg_{frame_idx:03d}.png")
                self._composite_title_frame(
                    bg_img=bg_img,
                    output_path=frame_path,
                    logo_img=logo_img,
                    title_text=episode_title,
                    avatars=avatars,
                    speakers_by_role=speakers_by_role,
                )
                segment_frames.append({
                    "path": frame_path,
                    "start_at": start_at,
                    "end_at": end_at,
                })
                frame_idx += 1
                continue

            item = items_by_id.get(news_item_id)
            if not item:
                continue

            # Get illustration for this item
            illust_path = illustration_paths.get(news_item_id)

            # Determine avatar(s) for this section
            script_data = item.script_data if isinstance(item.script_data, dict) else {}
            mode = script_data.get("mode", item.script_mode or "solo")

            if mode == "explainer" and script_data.get("dialogue"):
                # Split into per-turn frames with active speaker
                dialogue = script_data["dialogue"]
                total_chars = sum(len(t.get("text", "")) for t in dialogue)
                if total_chars == 0:
                    total_chars = 1
                section_duration = end_at - start_at
                turn_elapsed = start_at

                for turn in dialogue:
                    text = turn.get("text", "")
                    speaker = turn.get("speaker", "speaker_a")
                    turn_duration = section_duration * (len(text) / total_chars)
                    turn_end = turn_elapsed + turn_duration

                    # Map speaker key to role
                    active = "anchor" if speaker == "speaker_a" else "expert"

                    frame_path = os.path.join(frames_dir, f"seg_{frame_idx:03d}.png")
                    self._composite_frame(
                        bg_img=bg_img,
                        output_path=frame_path,
                        layout=LANDSCAPE,
                        illustration_path=illust_path,
                        avatars=avatars,
                        mode=mode,
                        speakers_by_role=speakers_by_role,
                        logo_img=logo_img,
                        topic_text=episode_title,
                        active_speaker=active,
                    )
                    segment_frames.append({
                        "path": frame_path,
                        "start_at": turn_elapsed,
                        "end_at": turn_end,
                    })
                    frame_idx += 1
                    turn_elapsed = turn_end
            else:
                # Solo mode or no dialogue: single frame for entire section
                frame_path = os.path.join(frames_dir, f"seg_{frame_idx:03d}.png")
                self._composite_frame(
                    bg_img=bg_img,
                    output_path=frame_path,
                    layout=LANDSCAPE,
                    illustration_path=illust_path,
                    avatars=avatars,
                    mode=mode,
                    speakers_by_role=speakers_by_role,
                    logo_img=logo_img,
                    topic_text=item.title,
                )
                segment_frames.append({
                    "path": frame_path,
                    "start_at": start_at,
                    "end_at": end_at,
                })
                frame_idx += 1

        logger.info("Generated %d segment frames in %s", len(segment_frames), frames_dir)
        return segment_frames

    @staticmethod
    def _load_avatars(speakers_by_role: dict[str, "SpeakerProfile"]) -> dict[str, Image.Image]:
        """Load avatar images from speaker profiles without resizing."""
        avatars: dict[str, Image.Image] = {}
        for role, sp in speakers_by_role.items():
            if sp.avatar_path and os.path.exists(sp.avatar_path):
                try:
                    avatars[role] = Image.open(sp.avatar_path).convert("RGBA")
                except Exception as e:
                    logger.warning("Failed to load avatar for %s: %s", role, e)
        return avatars

    def _composite_frame(
        self,
        bg_img: Image.Image,
        output_path: str,
        layout: FrameLayout,
        illustration_path: str | None = None,
        avatars: dict[str, Image.Image] | None = None,
        mode: str = "solo",
        speakers_by_role: dict[str, "SpeakerProfile"] | None = None,
        logo_img: Image.Image | None = None,
        topic_text: str = "",
        subtitle_text: str = "",
        active_speaker: str | None = None,
    ) -> None:
        """Compose a single frame using the given layout (landscape or portrait).

        Renders: background darkening, logo, topic text, illustration,
        avatar(s) with active-speaker highlighting, speaker names, and subtitle.
        """
        W, H = layout.width, layout.height
        canvas = bg_img.copy()
        canvas = canvas.resize((W, H), Image.Resampling.LANCZOS)

        # Darken background
        dark = Image.new("RGBA", (W, H), (0, 0, 0, layout.dark_alpha))
        canvas = Image.alpha_composite(canvas, dark)

        if avatars is None:
            avatars = {}
        if speakers_by_role is None:
            speakers_by_role = {}

        # --- Logo ---
        if logo_img:
            if layout.logo_centered:
                logo_x = (W - logo_img.width) // 2
            else:
                logo_x = 20
            canvas.paste(logo_img, (logo_x, layout.logo_y), logo_img if logo_img.mode == "RGBA" else None)

        # --- Topic text (if enabled) ---
        if layout.topic_fontsize > 0 and topic_text:
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            try:
                topic_font = ImageFont.truetype(FONT_PATH_BOLD, layout.topic_fontsize)
            except OSError:
                topic_font = ImageFont.load_default()

            display_topic = topic_text[:40] + "..." if len(topic_text) > 40 else topic_text
            topic_bbox = draw.textbbox((0, 0), display_topic, font=topic_font)
            topic_tw = topic_bbox[2] - topic_bbox[0]
            topic_th = topic_bbox[3] - topic_bbox[1]
            topic_x = (W - topic_tw) // 2
            bar_pad = 12
            draw.rounded_rectangle(
                [(topic_x - bar_pad, layout.topic_y - 4),
                 (topic_x + topic_tw + bar_pad, layout.topic_y + topic_th + 8)],
                radius=6, fill=(0, 0, 0, 180),
            )
            draw.text((topic_x, layout.topic_y), display_topic, font=topic_font, fill="white")
            canvas = Image.alpha_composite(canvas, overlay)

        # --- Illustration image ---
        if illustration_path and os.path.exists(illustration_path):
            try:
                illust = Image.open(illustration_path).convert("RGBA")
                illust = illust.resize((layout.illust_w, layout.illust_h), Image.Resampling.LANCZOS)
                if layout.illust_centered:
                    ix = (W - layout.illust_w) // 2
                else:
                    ix = layout.illust_x
                # White border effect
                border_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                border_draw = ImageDraw.Draw(border_overlay)
                border_draw.rounded_rectangle(
                    [(ix - 3, layout.illust_y - 3),
                     (ix + layout.illust_w + 3, layout.illust_y + layout.illust_h + 3)],
                    radius=10, fill=(255, 255, 255, 200),
                )
                canvas = Image.alpha_composite(canvas, border_overlay)
                canvas.paste(illust, (ix, layout.illust_y))
            except Exception as e:
                logger.warning("Failed to composite illustration: %s", e)

        # --- Avatar(s) ---
        av_size = layout.avatar_explainer_size
        gap = layout.avatar_explainer_gap
        if mode == "explainer":
            anchor_av = avatars.get("anchor")
            expert_av = avatars.get("expert")
            if anchor_av and expert_av:
                if layout.avatar_centered:
                    total_w = av_size * 2 + gap
                    start_x = (W - total_w) // 2
                    anchor_x = start_x
                    expert_x = start_x + av_size + gap
                else:
                    anchor_x = layout.avatar_base_x
                    expert_x = layout.avatar_base_x + av_size + gap

                anchor_resized = anchor_av.resize((av_size, av_size), Image.Resampling.LANCZOS)
                expert_resized = expert_av.resize((av_size, av_size), Image.Resampling.LANCZOS)

                # Dim inactive speaker
                if active_speaker and active_speaker != "anchor":
                    dim = Image.new("RGBA", anchor_resized.size, (0, 0, 0, 140))
                    anchor_resized = Image.alpha_composite(anchor_resized, dim)
                if active_speaker and active_speaker != "expert":
                    dim = Image.new("RGBA", expert_resized.size, (0, 0, 0, 140))
                    expert_resized = Image.alpha_composite(expert_resized, dim)

                # Active speaker border ring
                av_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                av_draw = ImageDraw.Draw(av_overlay)
                if active_speaker == "anchor":
                    av_draw.rounded_rectangle(
                        [(anchor_x - 4, layout.avatar_y - 4),
                         (anchor_x + av_size + 4, layout.avatar_y + av_size + 4)],
                        radius=8, outline=(100, 200, 255, 255), width=3,
                    )
                elif active_speaker == "expert":
                    av_draw.rounded_rectangle(
                        [(expert_x - 4, layout.avatar_y - 4),
                         (expert_x + av_size + 4, layout.avatar_y + av_size + 4)],
                        radius=8, outline=(100, 200, 255, 255), width=3,
                    )
                canvas = Image.alpha_composite(canvas, av_overlay)

                canvas.paste(anchor_resized, (anchor_x, layout.avatar_y), anchor_resized)
                canvas.paste(expert_resized, (expert_x, layout.avatar_y), expert_resized)

                # Speaker names below each avatar
                name_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                name_draw = ImageDraw.Draw(name_overlay)
                try:
                    name_font = ImageFont.truetype(FONT_PATH, layout.name_fontsize)
                except OSError:
                    name_font = ImageFont.load_default()
                anchor_sp = speakers_by_role.get("anchor")
                expert_sp = speakers_by_role.get("expert")
                anchor_color = (255, 255, 200) if active_speaker != "expert" else (150, 150, 130)
                expert_color = (200, 220, 255) if active_speaker != "anchor" else (130, 140, 160)
                if anchor_sp:
                    name_bbox = name_draw.textbbox((0, 0), anchor_sp.name, font=name_font)
                    name_w = name_bbox[2] - name_bbox[0]
                    name_draw.text(
                        (anchor_x + (av_size - name_w) // 2, layout.avatar_y + av_size + 4),
                        anchor_sp.name, font=name_font, fill=anchor_color,
                    )
                if expert_sp:
                    name_bbox = name_draw.textbbox((0, 0), expert_sp.name, font=name_font)
                    name_w = name_bbox[2] - name_bbox[0]
                    name_draw.text(
                        (expert_x + (av_size - name_w) // 2, layout.avatar_y + av_size + 4),
                        expert_sp.name, font=name_font, fill=expert_color,
                    )
                canvas = Image.alpha_composite(canvas, name_overlay)
            elif anchor_av:
                resized = anchor_av.resize((av_size, av_size), Image.Resampling.LANCZOS)
                if layout.avatar_centered:
                    ax = (W - av_size) // 2
                else:
                    ax = layout.avatar_base_x
                canvas.paste(resized, (ax, layout.avatar_y), resized)
            elif expert_av:
                resized = expert_av.resize((av_size, av_size), Image.Resampling.LANCZOS)
                if layout.avatar_centered:
                    ax = (W - av_size) // 2
                else:
                    ax = layout.avatar_base_x
                canvas.paste(resized, (ax, layout.avatar_y), resized)
        else:
            # Solo mode: narrator or anchor avatar
            solo_size = layout.avatar_solo_size
            narrator_av = avatars.get("narrator") or avatars.get("anchor")
            if narrator_av:
                resized = narrator_av.resize((solo_size, solo_size), Image.Resampling.LANCZOS)
                if layout.avatar_centered:
                    solo_x = (W - solo_size) // 2
                else:
                    solo_x = layout.avatar_base_x + (W - layout.avatar_base_x - solo_size) // 2
                canvas.paste(resized, (solo_x, layout.avatar_y), resized)
                sp = speakers_by_role.get("narrator") or speakers_by_role.get("anchor")
                if sp:
                    name_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    name_draw = ImageDraw.Draw(name_overlay)
                    try:
                        name_font = ImageFont.truetype(FONT_PATH, layout.name_fontsize)
                    except OSError:
                        name_font = ImageFont.load_default()
                    name_bbox = name_draw.textbbox((0, 0), sp.name, font=name_font)
                    name_w = name_bbox[2] - name_bbox[0]
                    name_draw.text(
                        (solo_x + (solo_size - name_w) // 2, layout.avatar_y + solo_size + 4),
                        sp.name, font=name_font, fill=(255, 255, 200),
                    )
                    canvas = Image.alpha_composite(canvas, name_overlay)

        # --- Subtitle text (if enabled) ---
        if layout.subtitle_fontsize > 0 and subtitle_text:
            display = re.sub(r'[（\(][ぁ-んー]+[）\)]', '', subtitle_text)
            try:
                sub_font = ImageFont.truetype(FONT_PATH_BOLD, layout.subtitle_fontsize)
            except OSError:
                sub_font = ImageFont.load_default()

            wrapped = textwrap.fill(display, width=layout.subtitle_wrap_width)
            lines = wrapped.split("\n")

            sub_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sub_draw = ImageDraw.Draw(sub_overlay)

            line_height = layout.subtitle_fontsize + 14
            total_h = len(lines) * line_height
            pad_y = 15
            sub_draw.rounded_rectangle(
                [(40, layout.subtitle_y - pad_y), (W - 40, layout.subtitle_y + total_h + pad_y)],
                radius=12, fill=(0, 0, 0, 180),
            )
            for i, line in enumerate(lines):
                lb = sub_draw.textbbox((0, 0), line, font=sub_font)
                lw = lb[2] - lb[0]
                lx = (W - lw) // 2
                ly = layout.subtitle_y + i * line_height
                sub_draw.text((lx, ly), line, font=sub_font, fill="white",
                              stroke_width=2, stroke_fill=(20, 20, 20))

            canvas = Image.alpha_composite(canvas, sub_overlay)

        # Save as RGB (FFmpeg needs no alpha)
        canvas.convert("RGB").save(output_path)

    def _composite_title_frame(
        self,
        bg_img: Image.Image,
        output_path: str,
        logo_img: Image.Image | None,
        title_text: str,
        avatars: dict[str, Image.Image],
        speakers_by_role: dict[str, "SpeakerProfile"],
    ) -> None:
        """Compose a title card frame for opening/transition/ending sections.

        Layout: darkened background + logo + centered title + avatars at bottom.
        """
        canvas = bg_img.copy()
        w, h = canvas.size

        # Darken background
        dark = Image.new("RGBA", (w, h), (0, 0, 0, 150))
        canvas = Image.alpha_composite(canvas, dark)

        # Logo top-left
        if logo_img:
            canvas.paste(logo_img, (20, 12), logo_img if logo_img.mode == "RGBA" else None)

        # Title text centered
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        fontsize = 36
        try:
            title_font = ImageFont.truetype(FONT_PATH_BOLD, fontsize)
        except OSError:
            title_font = ImageFont.load_default()

        # Wrap and center title
        display = title_text[:50] + "..." if len(title_text) > 50 else title_text
        title_bbox = draw.textbbox((0, 0), display, font=title_font)
        tw = title_bbox[2] - title_bbox[0]
        th = title_bbox[3] - title_bbox[1]
        tx = (w - tw) // 2
        ty = 180

        # Background bar
        bar_pad = 20
        draw.rounded_rectangle(
            [(tx - bar_pad, ty - 10), (tx + tw + bar_pad, ty + th + 14)],
            radius=10, fill=(0, 0, 0, 180),
        )
        draw.text((tx, ty), display, font=title_font, fill="white",
                  stroke_width=2, stroke_fill=(30, 30, 30))
        canvas = Image.alpha_composite(canvas, overlay)

        # Avatars at bottom center (horizontal)
        all_avatars = []
        for role in ["anchor", "expert", "narrator"]:
            if role in avatars:
                all_avatars.append((role, avatars[role]))

        if all_avatars:
            av_size = 140
            gap = 60
            total_w = len(all_avatars) * av_size + (len(all_avatars) - 1) * gap
            start_x = (w - total_w) // 2
            av_y = 280  # above center, well above subtitle area

            name_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            name_draw = ImageDraw.Draw(name_overlay)
            try:
                name_font = ImageFont.truetype(FONT_PATH, 14)
            except OSError:
                name_font = ImageFont.load_default()

            for i, (role, av) in enumerate(all_avatars):
                ax = start_x + i * (av_size + gap)
                resized = av.resize((av_size, av_size), Image.Resampling.LANCZOS)
                canvas.paste(resized, (ax, av_y), resized)

                sp = speakers_by_role.get(role)
                if sp:
                    nb = name_draw.textbbox((0, 0), sp.name, font=name_font)
                    nw = nb[2] - nb[0]
                    name_draw.text(
                        (ax + (av_size - nw) // 2, av_y + av_size + 4),
                        sp.name, font=name_font, fill=(255, 255, 200),
                    )
            canvas = Image.alpha_composite(canvas, name_overlay)

        canvas.convert("RGB").save(output_path)

    def _load_logo(self) -> Image.Image | None:
        """Load and resize the logo image for segment frame overlay."""
        if not settings.video_logo_enabled:
            return None
        logo_path = settings.video_logo_path
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                max_h = 50
                ratio = max_h / logo.height
                logo = logo.resize((int(logo.width * ratio), max_h), Image.Resampling.LANCZOS)
                return logo
            except Exception:
                pass
        # Generate text badge as image
        badge_img = Image.new("RGBA", (200, 40), (0, 0, 0, 0))
        badge_draw = ImageDraw.Draw(badge_img)
        try:
            badge_font = ImageFont.truetype(FONT_PATH_BOLD, 20)
        except OSError:
            badge_font = ImageFont.load_default()
        badge_draw.rounded_rectangle([(0, 0), (199, 39)], radius=6, fill=(220, 30, 30, 230))
        badge_draw.text((10, 8), "AI NEWS RADIO", font=badge_font, fill="white")
        return badge_img

    async def _generate_ai_metadata(
        self,
        prompt_key: str,
        user_prompt: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict | None:
        """Generate metadata via AI. Common provider/prompt/usage handling."""
        try:
            provider, model = get_step_provider("script")
            system_prompt, _ = await get_active_prompt(session, prompt_key)
            response = await provider.generate(prompt=user_prompt, model=model, system=system_prompt)
            data = parse_json_response(response.content)
            await self.record_usage(
                session=session,
                episode_id=episode_id,
                provider=response.provider,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
            return data
        except Exception as e:
            logger.warning("Metadata generation failed (%s): %s", prompt_key, e)
            return None

    async def _generate_youtube_metadata(
        self,
        episode: Episode,
        news_items: list[NewsItem],
        script_text: str,
        duration_seconds: float,
        timestamps: str,
        session: AsyncSession,
        speakers_by_role: dict[str, "SpeakerProfile"] | None = None,
    ) -> dict | None:
        """Generate YouTube metadata (title, description, tags) using AI."""
        news_summary = "\n".join(f"- {item.title}" for item in news_items)
        duration_min = int(duration_seconds // 60)
        duration_sec = int(duration_seconds % 60)

        timestamps_info = f"\n\nタイムスタンプ（正確な値）:\n{timestamps}" if timestamps else ""

        speakers_info = ""
        if speakers_by_role:
            speakers_lines = []
            role_labels = {"anchor": "MC", "expert": "解説", "narrator": "ナレーター"}
            for role in ["anchor", "expert", "narrator"]:
                sp = speakers_by_role.get(role)
                if sp:
                    label = role_labels.get(role, role)
                    desc = f"（{sp.description}）" if sp.description else ""
                    speakers_lines.append(f"- {sp.name}（{label}）{desc}")
            if speakers_lines:
                speakers_info = "\n\n出演者:\n" + "\n".join(speakers_lines)

        prompt = (
            f"番組タイトル: {episode.title}\n"
            f"ニュース一覧:\n{news_summary}\n"
            f"動画の長さ: {duration_min}分{duration_sec}秒\n\n"
            f"台本の冒頭300文字:\n{script_text[:300]}"
            f"{timestamps_info}"
            f"{speakers_info}"
        )

        data = await self._generate_ai_metadata(PROMPT_KEY, prompt, session, episode.id)
        if not data:
            return None

        logger.info("Episode %d: YouTube metadata generated", episode.id)
        return {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "tags": data.get("tags", []),
        }

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

    async def _ffmpeg_encode_video(
        self,
        audio_path: str,
        video_path: str,
        base_image_path: str,
        resolution: tuple[int, int],
        segment_frames: list[dict] | None = None,
        srt_path: str | None = None,
    ) -> None:
        """Generate MP4 video: base image + segment frame overlays + audio + optional subtitles.

        Args:
            resolution: (width, height) for the output video.
            srt_path: If provided, burn in SRT subtitles.
        """
        inputs = ["-i", base_image_path, "-i", audio_path]
        frames = segment_frames or []
        for frame in frames:
            inputs.extend(["-i", frame["path"]])

        w, h = resolution
        filter_parts = [
            f"[0:v]loop=loop=-1:size=1:start=0,"
            f"setpts=N/FRAME_RATE/TB,scale={w}:{h},setsar=1[base]"
        ]

        prev_label = "base"
        for i, frame in enumerate(frames):
            s = frame["start_at"]
            e = frame["end_at"]
            input_idx = i + 2
            out_label = f"seg{i}"
            filter_parts.append(
                f"[{prev_label}][{input_idx}:v]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'[{out_label}]"
            )
            prev_label = out_label

        if srt_path and os.path.exists(srt_path):
            escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            subtitle_marginv = 50 if frames else 30
            filter_parts.append(
                f"[{prev_label}]subtitles='{escaped_srt}'"
                f":force_style='FontName=Noto Sans CJK JP"
                f",FontSize=22,PrimaryColour=&H00FFFFFF"
                f",OutlineColour=&H00000000,BorderStyle=3"
                f",Outline=2,Shadow=1,BackColour=&H80000000"
                f",MarginV={subtitle_marginv}'"
                f"[v]"
            )
        else:
            filter_parts.append(f"[{prev_label}]null[v]")

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
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

        logger.info("FFmpeg completed: %s (%d segment frames)", video_path, len(frames))

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
        # Use precise start_at/end_at from voice step when available,
        # fall back to cumulative calculation for backward compatibility
        silence_gap = settings.voice_section_silence
        raw_entries: list[tuple[float, float, str]] = []
        fallback_elapsed = 0.0

        for sec in voice_sections:
            key = sec.get("key", "")
            duration = sec.get("duration_seconds", 0.0)
            text = section_texts.get(key, "")

            # Determine section start/end: prefer precise timestamps
            if "start_at" in sec and "end_at" in sec:
                section_start = sec["start_at"]
                section_end = sec["end_at"]
                section_duration = section_end - section_start
            else:
                section_start = fallback_elapsed
                section_duration = duration
                section_end = section_start + section_duration

            if text and section_duration > 0:
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

                sub_elapsed = section_start
                for sentence in sentences:
                    ratio = len(sentence) / total_chars
                    sub_duration = section_duration * ratio
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

            fallback_elapsed += duration + silence_gap

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
        if settings.video_logo_enabled:
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

    # ------------------------------------------------------------------
    # Shorts video generation
    # ------------------------------------------------------------------

    async def _generate_shorts_videos(
        self,
        episode_id: int,
        shorts_data: list[dict],
        news_items: list[NewsItem],
        illustration_paths: dict[int, str],
        bg_image_path: str,
        speakers_by_role: dict[str, "SpeakerProfile"],
        session: AsyncSession,
        episode_dir: str,
    ) -> list[dict]:
        """Generate short videos (vertical 9:16) for all shorts."""
        shorts_dir = os.path.join(episode_dir, "shorts")
        os.makedirs(shorts_dir, exist_ok=True)

        items_by_id: dict[int, NewsItem] = {item.id: item for item in news_items}
        results: list[dict] = []
        sem = asyncio.Semaphore(2)

        async def _gen_one(short: dict) -> dict | None:
            async with sem:
                news_item_id = short.get("news_item_id")
                if not news_item_id:
                    return None

                audio_file = short.get("file", "")
                if not audio_file:
                    return None

                audio_full = os.path.join(settings.media_dir, audio_file)
                if not os.path.exists(audio_full):
                    logger.warning("Short audio not found: %s", audio_full)
                    return None

                mode = short.get("mode", "solo")
                duration = short.get("duration_seconds", 0.0)
                caption = short.get("caption", "")
                dialogue = short.get("dialogue", [])

                item = items_by_id.get(news_item_id)
                illust_path = illustration_paths.get(news_item_id)

                video_filename = f"short_{news_item_id}.mp4"
                video_path = os.path.join(shorts_dir, video_filename)

                if settings.shorts_video_provider == "veo":
                    await self._generate_short_video_veo(
                        caption=caption,
                        audio_path=audio_full,
                        video_path=video_path,
                        illust_path=illust_path,
                        session=session,
                        episode_id=episode_id,
                    )
                else:
                    await self._generate_short_video_ffmpeg(
                        audio_path=audio_full,
                        video_path=video_path,
                        bg_image_path=bg_image_path,
                        illust_path=illust_path,
                        mode=mode,
                        dialogue=dialogue,
                        caption=caption,
                        speakers_by_role=speakers_by_role,
                        item=item,
                        duration=duration,
                    )

                # Generate metadata
                metadata = await self._generate_shorts_metadata(
                    caption=caption,
                    item=item,
                    session=session,
                    episode_id=episode_id,
                )

                return {
                    "news_item_id": news_item_id,
                    "video_path": f"{episode_id}/shorts/{video_filename}",
                    "duration_seconds": duration,
                    "mode": mode,
                    "provider": settings.shorts_video_provider,
                    "metadata": metadata,
                }

        tasks = [_gen_one(s) for s in shorts_data]
        gen_results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in gen_results:
            if isinstance(r, dict):
                results.append(r)
            elif isinstance(r, Exception):
                logger.warning("Short video generation failed: %s", r)

        logger.info("Episode %d: generated %d/%d short videos", episode_id, len(results), len(shorts_data))
        return results

    async def _generate_short_video_ffmpeg(
        self,
        audio_path: str,
        video_path: str,
        bg_image_path: str,
        illust_path: str | None,
        mode: str,
        dialogue: list[dict],
        caption: str,
        speakers_by_role: dict[str, "SpeakerProfile"],
        item: NewsItem | None,
        duration: float,
    ) -> None:
        """Generate a short video (1080x1920) using Pillow frames + FFmpeg."""
        # Load background
        try:
            bg_img = Image.open(bg_image_path).convert("RGBA")
        except Exception:
            bg_img = Image.new("RGBA", (1080, 1920), (26, 26, 46, 255))

        logo_img = self._load_logo()
        avatars = self._load_avatars(speakers_by_role)

        frames_dir = os.path.dirname(video_path)
        os.makedirs(frames_dir, exist_ok=True)

        segment_frames: list[dict] = []
        frame_idx = 0

        if mode == "explainer" and dialogue:
            total_chars = sum(len(t.get("text", "")) for t in dialogue)
            if total_chars == 0:
                total_chars = 1
            elapsed = 0.0

            for turn in dialogue:
                text = turn.get("text", "")
                speaker = turn.get("speaker", "speaker_a")
                turn_duration = duration * (len(text) / total_chars)
                turn_end = elapsed + turn_duration
                active = "anchor" if speaker == "speaker_a" else "expert"

                frame_path = os.path.join(frames_dir, f"short_frame_{frame_idx:03d}.png")
                self._composite_frame(
                    bg_img=bg_img,
                    output_path=frame_path,
                    layout=PORTRAIT,
                    illustration_path=illust_path,
                    avatars=avatars,
                    mode=mode,
                    speakers_by_role=speakers_by_role,
                    logo_img=logo_img,
                    subtitle_text=text,
                    active_speaker=active,
                )
                segment_frames.append({
                    "path": frame_path,
                    "start_at": elapsed,
                    "end_at": turn_end,
                })
                frame_idx += 1
                elapsed = turn_end
        else:
            subtitle = caption or (item.title if item else "")
            frame_path = os.path.join(frames_dir, f"short_frame_{frame_idx:03d}.png")
            self._composite_frame(
                bg_img=bg_img,
                output_path=frame_path,
                layout=PORTRAIT,
                illustration_path=illust_path,
                avatars=avatars,
                mode=mode,
                speakers_by_role=speakers_by_role,
                logo_img=logo_img,
                subtitle_text=subtitle,
            )
            segment_frames.append({
                "path": frame_path,
                "start_at": 0.0,
                "end_at": duration,
            })

        # FFmpeg encode
        await self._ffmpeg_encode_video(
            audio_path=audio_path,
            video_path=video_path,
            base_image_path=segment_frames[0]["path"],
            resolution=(1080, 1920),
            segment_frames=segment_frames,
        )

    async def _generate_short_video_veo(
        self,
        caption: str,
        audio_path: str,
        video_path: str,
        illust_path: str | None,
        session: AsyncSession,
        episode_id: int,
    ) -> None:
        """Generate short video using Veo image-to-video API, then merge audio.

        If an illustration image is available, it is passed as a reference image
        (asset type) so Veo generates a video that incorporates the illustration's
        content. This produces more visually relevant shorts than text-only prompts.
        """
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise RuntimeError("google-genai package required for Veo provider")

        client = genai.Client(api_key=settings.google_api_key)
        prompt = (
            f"この画像を元に、ニュース解説の短い動画を作成してください。"
            f"画像の内容を活かしつつ、緩やかなカメラワークやズームで動きをつけてください。"
            f"テーマ: {caption}。"
            f"プロフェッショナルなニュース番組のスタイルで。"
        )

        # Build reference images from illustration
        reference_images: list = []
        if illust_path and os.path.exists(illust_path):
            try:
                ref_image = types.Image.from_file(illust_path)
                reference_images.append(
                    types.VideoGenerationReferenceImage(
                        image=ref_image,
                        reference_type="asset",
                    )
                )
                logger.info("Veo: using illustration as reference image: %s", illust_path)
            except Exception as e:
                logger.warning("Failed to load reference image for Veo: %s", e)

        config = types.GenerateVideosConfig(
            aspect_ratio="9:16",
            number_of_videos=1,
        )
        # Reference images require Veo 3.0+; skip for Veo 2.x
        if reference_images and "veo-2" not in settings.visual_veo_model:
            config.reference_images = reference_images
        elif reference_images:
            logger.warning("Veo 2.x does not support reference images; falling back to text-only. "
                           "Set visual_veo_model to veo-3.0+ for image-to-video.")

        operation = client.models.generate_videos(
            model=settings.visual_veo_model,
            prompt=prompt,
            config=config,
        )

        # Poll for completion
        while not operation.done:
            await asyncio.sleep(5)
            operation = client.operations.get(operation)

        video_data = operation.result.generated_videos[0]
        # Save raw Veo video to temp file
        temp_video = video_path + ".veo.mp4"
        client.files.download(file=video_data.video, download_path=temp_video)

        # Merge Veo video with audio using FFmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", temp_video,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            video_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg Veo merge failed: {stderr.decode()}")

        # Clean up temp file
        try:
            os.remove(temp_video)
        except OSError:
            pass

        # Record cost (Veo pricing)
        await self.record_usage(
            session=session,
            episode_id=episode_id,
            provider="google-veo",
            model=settings.visual_veo_model,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.35,  # Approximate per-video cost
        )

        logger.info("Veo short video generated: %s", video_path)

    async def _generate_shorts_metadata(
        self,
        caption: str,
        item: NewsItem | None,
        session: AsyncSession,
        episode_id: int,
    ) -> dict | None:
        """Generate YouTube Shorts metadata (title, description, hashtags) using AI."""
        title = item.title if item else caption
        summary = caption or (item.script_text[:200] if item and item.script_text else "")

        prompt = (
            f"ニュースタイトル: {title}\n"
            f"要約: {summary}\n"
        )

        data = await self._generate_ai_metadata(SHORTS_PROMPT_KEY, prompt, session, episode_id)
        if not data:
            return None

        return {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "hashtags": data.get("hashtags", []),
        }

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
