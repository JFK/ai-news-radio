"""Step 4: Script generation pipeline step."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import NewsItem, StepName
from app.pipeline.base import BaseStep
from app.pipeline.utils import parse_json_response
from app.services.ai_provider import get_step_provider

logger = logging.getLogger(__name__)

SCRIPT_ITEM_SYSTEM_PROMPT = """\
あなたはラジオニュース番組の台本を書く放送作家です。

以下のルールに従って、1つのニュースについての台本を書いてください:

## 台本構成ルール
1. **導入（10秒）**: 「ひとことで言うと〜」で要点を伝える
2. **背景解説（30秒）**: なぜ重要か、経緯をストーリーで。専門用語はその場で言い換え
3. **クリティカル分析（30秒）**: 情報源の信頼性、異なる立場からの見方を最低2つ、数字はスケール比較
4. **生活への影響（15秒）**: 「私たちの暮らしにどう関係するか」を具体的に
5. **締め（10秒）**: リスナーへの問いかけ or 考えるヒントで終わる（断定的な結論は避ける）

## 禁止事項
- 情報源不明の断定
- 煽り・恐怖訴求
- 一方的な立場の押し付け
- 専門用語の説明なし使用

## 話し方
- 親しみやすいが知的なトーン
- 「〜ですね」「〜なんです」など、ラジオらしい語りかけ口調
- 難しい数字は身近なスケールに置き換える

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "script_text": "台本の全文テキスト"
}"""

SCRIPT_EPISODE_SYSTEM_PROMPT = """\
あなたはラジオニュース番組の構成作家です。

個別のニュース台本が用意されています。これらを1つの番組として構成してください。

以下の要素を生成してください:
1. **オープニング**: 番組の冒頭挨拶と今日のトピック紹介（30秒程度）
2. **つなぎ**: 各ニュースの間をつなぐ短いコメント
3. **エンディング**: 番組の締めくくり（20秒程度）

コンセプト: 「ニュースを読むだけじゃない。一緒に考えるラジオ。」

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "opening": "オープニングの台本テキスト",
  "transitions": ["ニュース1→2のつなぎ", "ニュース2→3のつなぎ"],
  "ending": "エンディングの台本テキスト"
}"""


class ScriptwriterStep(BaseStep):
    """Generate radio scripts from analyzed news articles."""

    @property
    def step_name(self) -> StepName:
        return StepName.SCRIPT

    async def execute(self, episode_id: int, input_data: dict) -> dict:
        """Generate scripts in two phases.

        Phase 1: Per-article script generation (N AI calls)
        Phase 2: Episode composition (1 AI call)
        """
        provider, model = get_step_provider(self.step_name.value)
        item_scripts: list[dict] = []
        total_input_tokens = 0
        total_output_tokens = 0

        async with async_session() as session:
            items = await self._get_news_items(episode_id, session)

            # Phase 1: per-article scripts
            for item in items:
                result = await self._script_item(item, provider, model, session, episode_id)
                item_scripts.append(result)
                total_input_tokens += result["input_tokens"]
                total_output_tokens += result["output_tokens"]

            # Phase 2: episode composition
            episode_script = await self._compose_episode(item_scripts, provider, model, session, episode_id)
            total_input_tokens += episode_script["input_tokens"]
            total_output_tokens += episode_script["output_tokens"]

            await session.commit()

        logger.info("Episode %d: scripted %d items + episode composition", episode_id, len(items))

        return {
            "items_scripted": len(item_scripts),
            "item_scripts": [{"news_item_id": s["news_item_id"], "title": s["title"]} for s in item_scripts],
            "episode_script": episode_script["full_script"],
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        }

    async def _get_news_items(self, episode_id: int, session: AsyncSession) -> list[NewsItem]:
        """Load all NewsItems for the episode."""
        result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode_id).order_by(NewsItem.id))
        return list(result.scalars().all())

    async def _script_item(
        self,
        item: NewsItem,
        provider,
        model: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict:
        """Generate a script for a single news item."""
        analysis_info = ""
        if item.analysis_data:
            ad = item.analysis_data
            perspectives_text = ""
            for p in ad.get("perspectives", []):
                perspectives_text += f"  - {p.get('standpoint', '')}: {p.get('argument', '')}\n"

            analysis_info = (
                f"\n\n分析結果:\n"
                f"- 背景: {ad.get('background', '(なし)')}\n"
                f"- なぜ今: {ad.get('why_now', '(なし)')}\n"
                f"- 複数視点:\n{perspectives_text}"
                f"- データ検証: {ad.get('data_validation', '(なし)')}\n"
                f"- 生活への影響: {ad.get('impact', '(なし)')}\n"
                f"- 不確実性: {ad.get('uncertainties', '(なし)')}"
            )

        fact_check_info = ""
        if item.fact_check_status:
            fact_check_info = (
                f"\n\nファクトチェック:\n- ステータス: {item.fact_check_status}\n- スコア: {item.fact_check_score}/5"
            )

        prompt = (
            f"タイトル: {item.title}\n"
            f"ソース: {item.source_name}\n"
            f"要約: {item.summary or '(なし)'}"
            f"{fact_check_info}"
            f"{analysis_info}"
        )

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=SCRIPT_ITEM_SYSTEM_PROMPT,
        )

        data = parse_json_response(response.content)
        item.script_text = data.get("script_text", "")

        await self.record_usage(
            session=session,
            episode_id=episode_id,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        return {
            "news_item_id": item.id,
            "title": item.title,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

    async def _compose_episode(
        self,
        item_scripts: list[dict],
        provider,
        model: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict:
        """Compose the full episode script with opening, transitions, and ending."""
        # Build summary of all news items for the composition prompt
        items_summary = ""
        for i, script in enumerate(item_scripts, 1):
            items_summary += f"\nニュース{i}: {script['title']}"

        # Reload items to get their script_text
        result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode_id).order_by(NewsItem.id))
        items = list(result.scalars().all())

        scripts_text = ""
        for i, item in enumerate(items, 1):
            scripts_text += f"\n\n--- ニュース{i}: {item.title} ---\n{item.script_text or '(台本なし)'}"

        prompt = f"今日のニュース一覧:{items_summary}\n\n各ニュースの台本:{scripts_text}"

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=SCRIPT_EPISODE_SYSTEM_PROMPT,
        )

        data = parse_json_response(response.content)

        await self.record_usage(
            session=session,
            episode_id=episode_id,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

        # Build full episode script
        opening = data.get("opening", "")
        transitions = data.get("transitions", [])
        ending = data.get("ending", "")

        full_script_parts = [opening]
        for i, item in enumerate(items):
            if item.script_text:
                full_script_parts.append(item.script_text)
            if i < len(transitions):
                full_script_parts.append(transitions[i])
        full_script_parts.append(ending)

        full_script = "\n\n".join(full_script_parts)

        return {
            "opening": opening,
            "transitions": transitions,
            "ending": ending,
            "full_script": full_script,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }
