"""Generate note.com markdown articles and cover images from episode data."""

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ApiUsage, Episode, NewsItem
from app.services.ai_provider import AIResponse, get_provider
from app.services.cost_estimator import estimate_cost
from app.services.prompt_loader import get_active_prompt, register_default
from app.services.visual_provider import get_visual_provider

logger = logging.getLogger(__name__)

# --- Analysis article prompt ---

ANALYSIS_PROMPT_KEY = "note_analysis_article"

ANALYSIS_SYSTEM_PROMPT = """\
あなたはニュース分析結果を、note.comに投稿するマークダウン記事に変換する専門ライターです。

## 記事構成
1. **タイトル**（H1）: 読者の関心を引く、具体的でわかりやすいタイトル
2. **リード文**: 3行以内で記事の要点
3. **各ニュースの解説**: 背景・クリティカル分析・生活への影響
4. **まとめ**: 全体を俯瞰した考察と読者への問いかけ
5. **ソース一覧**: 参照元リンク

## 文体
- 「です・ます」調
- 専門用語はその場で言い換え
- 断定を避け、複数の視点を公平に提示
- 1段落3-4行以内

## note.com最適化
- 見出し（##）を効果的に使用
- 引用（>）で重要ポイント強調
- 箇条書きで複数視点を整理"""

register_default(ANALYSIS_PROMPT_KEY, ANALYSIS_SYSTEM_PROMPT)

# --- Video article prompt ---

VIDEO_PROMPT_KEY = "note_video_article"

VIDEO_SYSTEM_PROMPT = """\
あなたはYouTube動画の紹介記事を、note.comに投稿するマークダウン記事に変換する専門ライターです。

## 記事構成
1. **タイトル**（H1）: 動画内容を反映した魅力的なタイトル
2. **動画リンク**: YouTube URLプレースホルダー
3. **概要**: 動画で取り上げた話題の要約
4. **ハイライト**: 見どころを箇条書き
5. **各ニュースの要点**: ニュースごとの簡潔なまとめ
6. **おわりに**: チャンネル登録の案内

## 文体
- 「です・ます」調
- カジュアルすぎず堅すぎないトーン
- 動画を見たくなる期待感

## note.com最適化
- 見出し（##）を効果的に使用
- YouTube URL は {{YOUTUBE_URL}} プレースホルダー"""

register_default(VIDEO_PROMPT_KEY, VIDEO_SYSTEM_PROMPT)


def _build_items_text(news_items: list[NewsItem]) -> str:
    """Build text representation of news items for AI prompt."""
    items_text = ""
    for i, item in enumerate(news_items):
        items_text += f"\n## ニュース {i + 1}: {item.title}\n"
        items_text += f"ソース: {item.source_name} ({item.source_url})\n"
        if item.summary:
            items_text += f"要約: {item.summary}\n"
        if item.fact_check_score is not None:
            items_text += f"ファクトチェックスコア: {item.fact_check_score}/5\n"
        if item.fact_check_details:
            items_text += f"ファクトチェック詳細: {item.fact_check_details}\n"
        if item.analysis_data:
            ad = item.analysis_data
            if ad.get("background"):
                items_text += f"背景: {ad['background']}\n"
            if ad.get("why_now"):
                items_text += f"なぜ今: {ad['why_now']}\n"
            if ad.get("perspectives"):
                items_text += "視点:\n"
                for p in ad["perspectives"]:
                    items_text += (
                        f"  - {p.get('standpoint', '不明')}: {p.get('argument', '')} (根拠: {p.get('basis', '')})\n"
                    )
            if ad.get("data_validation"):
                items_text += f"データ検証: {ad['data_validation']}\n"
            if ad.get("impact"):
                items_text += f"影響評価: {ad['impact']}\n"
            if ad.get("uncertainties"):
                items_text += f"不確実性: {ad['uncertainties']}\n"
            if ad.get("source_comparison"):
                items_text += f"ソース比較: {ad['source_comparison']}\n"
        items_text += "\n"
    return items_text


async def _record_usage(
    session: AsyncSession,
    episode: Episode,
    response: AIResponse,
) -> None:
    """Record API usage for note export."""
    cost = await estimate_cost(session, response.model, response.input_tokens, response.output_tokens)
    session.add(
        ApiUsage(
            episode_id=episode.id,
            step_name="note_export",
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=cost,
        )
    )
    await session.commit()


async def generate_note_analysis(
    episode: Episode,
    news_items: list[NewsItem],
    session: AsyncSession,
) -> tuple[str, int, int]:
    """Generate a note.com analysis article from episode analysis data.

    Returns:
        Tuple of (markdown, input_tokens, output_tokens).
    """
    provider_name = settings.pipeline_export_provider or settings.default_ai_provider
    model = settings.pipeline_export_model or settings.default_ai_model
    provider = get_provider(provider_name)

    system_prompt, _ = await get_active_prompt(session, ANALYSIS_PROMPT_KEY)

    items_text = _build_items_text(news_items)
    user_prompt = (
        f"# エピソード: {episode.title}\n\n"
        f"以下の{len(news_items)}件のニュース分析結果を、"
        f"note.com用のマークダウン記事に変換してください。\n"
        f"{items_text}"
    )

    response: AIResponse = await provider.generate(
        prompt=user_prompt,
        model=model,
        system=system_prompt,
    )

    await _record_usage(session, episode, response)
    return response.content, response.input_tokens, response.output_tokens


async def generate_note_video(
    episode: Episode,
    news_items: list[NewsItem],
    video_output: dict | None,
    session: AsyncSession,
) -> tuple[str, int, int]:
    """Generate a note.com video introduction article.

    Returns:
        Tuple of (markdown, input_tokens, output_tokens).
    """
    provider_name = settings.pipeline_export_provider or settings.default_ai_provider
    model = settings.pipeline_export_model or settings.default_ai_model
    provider = get_provider(provider_name)

    system_prompt, _ = await get_active_prompt(session, VIDEO_PROMPT_KEY)

    items_text = _build_items_text(news_items)

    # Add video metadata if available
    video_info = ""
    if video_output:
        yt_meta = video_output.get("youtube_metadata", {})
        if yt_meta:
            if yt_meta.get("title"):
                video_info += f"動画タイトル: {yt_meta['title']}\n"
            if yt_meta.get("description"):
                video_info += f"動画概要: {yt_meta['description']}\n"
            if yt_meta.get("tags"):
                video_info += f"タグ: {', '.join(yt_meta['tags'])}\n"

    user_prompt = f"# エピソード: {episode.title}\n\n"
    if video_info:
        user_prompt += f"## 動画メタデータ\n{video_info}\n"
    user_prompt += (
        f"以下の{len(news_items)}件のニュースを取り上げたYouTube動画の紹介記事を、"
        f"note.com用のマークダウンで作成してください。\n"
        f"{items_text}"
    )

    response: AIResponse = await provider.generate(
        prompt=user_prompt,
        model=model,
        system=system_prompt,
    )

    await _record_usage(session, episode, response)
    return response.content, response.input_tokens, response.output_tokens


async def generate_note_cover_image(
    episode: Episode,
    news_items: list[NewsItem],
    article_type: str,
    session: AsyncSession,
) -> str:
    """Generate a cover image for a note.com article using AI prompt + Imagen.

    Returns:
        Relative media path to the generated image.
    """
    provider_name = settings.pipeline_export_provider or settings.default_ai_provider
    model = settings.pipeline_export_model or settings.default_ai_model
    ai_provider = get_provider(provider_name)

    topics = ", ".join(item.title for item in news_items[:5])
    prompt_request = (
        f"Generate a short (1-2 sentences) image prompt in English for an Imagen 4 model.\n"
        f"The image is a cover/header for a note.com article about: {episode.title}\n"
        f"Topics covered: {topics}\n"
        f"Requirements:\n"
        f"- Abstract, editorial-style illustration\n"
        f"- No text, no letters, no words, no watermarks\n"
        f"- Suitable for a news analysis blog post\n"
        f"- Visually appealing, professional\n"
        f"Return ONLY the image prompt, nothing else."
    )

    response: AIResponse = await ai_provider.generate(
        prompt=prompt_request,
        model=model,
        system="You are an image prompt generator. Return only the image generation prompt.",
    )

    await _record_usage(session, episode, response)

    image_prompt = response.content.strip()
    logger.info("Generated cover image prompt: %s", image_prompt)

    episode_dir = os.path.join(settings.media_dir, str(episode.id))
    os.makedirs(episode_dir, exist_ok=True)
    filename = f"note_cover_{article_type}.png"
    output_path = os.path.join(episode_dir, filename)

    visual = get_visual_provider()
    await visual.generate_background_image(image_prompt, output_path)

    # Record Imagen cost ($0.04 per image for Imagen 4)
    if settings.visual_provider == "google":
        session.add(
            ApiUsage(
                episode_id=episode.id,
                step_name="note_export",
                provider="google-imagen",
                model=settings.visual_imagen_model,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.04,
            )
        )
        await session.commit()

    return f"{episode.id}/{filename}"
