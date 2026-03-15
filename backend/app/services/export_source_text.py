"""Generate NotebookLM source text from episode analysis data."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ApiUsage, Episode, NewsItem, Pronunciation
from app.services.ai_provider import AIResponse, get_provider
from app.services.cost_estimator import estimate_cost
from app.services.prompt_loader import get_active_prompt, register_default

logger = logging.getLogger(__name__)

PROMPT_KEY = "export_notebooklm"

EXPORT_SYSTEM_PROMPT = """\
あなたはニュース分析結果を、Google NotebookLM の Audio Overview（ポッドキャスト生成）に最適なソーステキストに変換する専門家です。

与えられた分析データを基に、以下の要件を満たすソーステキストを生成してください:

## 形式

- 1つの長文テキストとして出力（JSON不要）
- 明確なセクション構成（見出し付き）
- 各ニュースごとに「背景」「複数の視点」「データの読み方」「生活への影響」を網羅
- ニュース間の関連性や共通テーマがあれば言及

## NotebookLM最適化

- **議論ポイント**を明示する（「ここで注目すべきは〜」「一方で〜という見方もある」）
- **問いかけ**を含める（「なぜこのタイミングで〜」「これは本当に〜なのか」）
- **不確実な点**は明確に区別する（「確認されている事実」vs「推測・見込み」）
- 専門用語には簡潔な説明を添える

## 読み方ガイド（音声生成の読み間違い防止）

- 地名・人名・組織名・専門用語など、読み間違えやすい固有名詞には初出時に「漢字（よみ）」形式で読みを付ける
  - 例: 健軍（けんぐん）、阿蘇（あそ）、益城（ましき）
- 一般的な漢字でも文脈で読みが変わるもの（例: 大分＝おおいた）にも付ける
- 同じ語の2回目以降は読みを省略してよい
- 以下の読み辞書が登録されている場合、その読みに従うこと:
{reading_dict_section}

## コンテンツ方針

- 情報源の信頼性を明示
- 複数の立場からの見方を公平に提示
- 数字・データにはスケール比較を添える
- 断定を避け、考えるヒントを提供する"""

register_default(PROMPT_KEY, EXPORT_SYSTEM_PROMPT)

INSTRUCTIONS_KEY = "export_notebooklm_instructions"

NOTEBOOKLM_INSTRUCTIONS = """\
## AIホストへの指示

以下のソーステキストをもとにポッドキャストを生成してください。

### 焦点を当てるべきこと
- 各ニュースの「なぜ重要か」「私たちの生活にどう影響するか」を中心に解説
- 複数の視点を公平に紹介し、リスナーが自分で考えられる材料を提供
- 専門用語は必ずわかりやすく言い換える

### トーンとスタイル
- 落ち着いた、信頼感のあるトーン
- 断定を避け、「〜という見方もあります」「〜の可能性があります」を使う
- リスナーへの問いかけを入れて、考えるきっかけを作る

### 構成
- 冒頭で今日のトピック一覧を簡潔に紹介
- 各ニュースの解説後に、短い振り返りや問いかけを入れる
- 最後に全体のまとめと、リスナーへのメッセージで締める

---

"""

register_default(INSTRUCTIONS_KEY, NOTEBOOKLM_INSTRUCTIONS)


async def generate_source_text(
    episode: Episode,
    news_items: list[NewsItem],
    session: AsyncSession,
) -> tuple[str, int, int]:
    """Generate NotebookLM source text from analysis data.

    Args:
        episode: The episode to export.
        news_items: Non-excluded news items with analysis_data populated.
        session: DB session for usage tracking.

    Returns:
        Tuple of (source_text, input_tokens, output_tokens).
    """
    # Determine provider/model
    provider_name = settings.pipeline_export_provider or settings.default_ai_provider
    model = settings.pipeline_export_model or settings.default_ai_model
    provider = get_provider(provider_name)

    system_prompt, _ = await get_active_prompt(session, PROMPT_KEY)

    # Load pronunciation dictionary and inject into system prompt
    pron_result = await session.execute(
        select(Pronunciation).order_by(Pronunciation.priority.desc(), Pronunciation.id)
    )
    pronunciations = list(pron_result.scalars().all())
    if pronunciations:
        dict_lines = "\n".join(f"  - {e.surface} → {e.reading}" for e in pronunciations)
        reading_dict = f"\n{dict_lines}"
    else:
        reading_dict = "\n  （登録なし — AIが自動判断してください）"
    system_prompt = system_prompt.replace("{reading_dict_section}", reading_dict)

    # Build user prompt from analysis data
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
                        f"  - {p.get('standpoint', '不明')}: "
                        f"{p.get('argument', '')} "
                        f"(根拠: {p.get('basis', '')})\n"
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

    user_prompt = (
        f"# エピソード: {episode.title}\n\n"
        f"以下の{len(news_items)}件のニュース分析結果を、"
        f"NotebookLM Audio Overview用のソーステキストに変換してください。\n"
        f"{items_text}"
    )

    response: AIResponse = await provider.generate(
        prompt=user_prompt,
        model=model,
        system=system_prompt,
    )

    # Record API usage
    cost = await estimate_cost(session, response.model, response.input_tokens, response.output_tokens)
    usage = ApiUsage(
        episode_id=episode.id,
        step_name="export",
        provider=response.provider,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=cost,
    )
    session.add(usage)
    await session.commit()

    # Prepend NotebookLM instructions to the generated source text
    instructions, _ = await get_active_prompt(session, INSTRUCTIONS_KEY)
    source_text = instructions + response.content if instructions else response.content

    # Apply pronunciation dictionary as reading hints (safety net for AI misses)
    if pronunciations:
        source_text = _apply_reading_hints(source_text, pronunciations)

    # Append source URLs
    source_text += "\n\n---\n\n## 情報ソース一覧\n\n"
    for i, item in enumerate(news_items):
        source_text += f"{i + 1}. [{item.title}]({item.source_url}) — {item.source_name}\n"

    return source_text, response.input_tokens, response.output_tokens


def _apply_reading_hints(text: str, pronunciations: list[Pronunciation]) -> str:
    """Insert reading hints like 健軍（けんぐん） for NotebookLM pronunciation.

    Unlike TTS which replaces kanji with kana, NotebookLM needs the original
    text preserved with reading hints so it can display and pronounce correctly.
    Skips if the hint is already present to avoid duplication.
    """
    for entry in pronunciations:
        hint = f"{entry.surface}（{entry.reading}）"
        # Skip if already annotated
        if hint in text:
            continue
        # Replace only the first occurrence with hint, leave subsequent as-is
        # (NotebookLM only needs the hint once to learn the pronunciation)
        text = text.replace(entry.surface, hint, 1)
    return text
