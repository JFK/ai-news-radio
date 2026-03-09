"""Step 3: Critical analysis pipeline step."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import NewsItem, StepName
from app.pipeline.base import BaseStep
from app.pipeline.utils import parse_json_response
from app.services.ai_provider import get_step_provider

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """\
あなたはニュースのクリティカル分析を行う専門家です。

与えられたニュース記事とファクトチェック結果に基づき、以下の観点で分析してください:

1. **背景・文脈**: このニュースの背景にある経緯や状況
2. **「なぜ今」**: このニュースが今出てきた理由、タイミングの意味
3. **複数視点**: 最低3つの異なる立場からの見方（賛成・反対・中立など）
4. **データ検証**: 記事中の数字やデータの妥当性、比較対象の適切さ
5. **生活への影響**: このニュースが一般市民の生活にどう影響するか
6. **不確実性**: わからないこと、確認できないことは明示する

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "background": "背景・文脈の説明",
  "why_now": "なぜ今このニュースが出てきたのかの分析",
  "perspectives": [
    {
      "standpoint": "立場（例: 行政側、住民側、専門家）",
      "argument": "その立場からの主張",
      "basis": "主張の根拠"
    }
  ],
  "data_validation": "データや数字の検証結果",
  "impact": "一般市民の生活への具体的な影響",
  "uncertainties": "不確実な点、確認できない点",
  "severity": "high または medium または low（ニュースの重要度）",
  "topics": ["関連トピックタグ1", "関連トピックタグ2"]
}"""


class AnalyzerStep(BaseStep):
    """Critically analyze news articles using AI."""

    @property
    def step_name(self) -> StepName:
        return StepName.ANALYSIS

    async def execute(self, episode_id: int, input_data: dict, **kwargs) -> dict:
        """Analyze each NewsItem for the episode.

        Uses fact-check results in the prompt for context.
        One AI call per article. Idempotent: re-running overwrites previous results.
        """
        provider, model = get_step_provider(self.step_name.value)
        results: list[dict] = []
        total_input_tokens = 0
        total_output_tokens = 0

        async with async_session() as session:
            items = await self._get_news_items(episode_id, session)

            for item in items:
                result = await self._analyze_item(item, provider, model, session, episode_id)
                results.append(result)
                total_input_tokens += result["input_tokens"]
                total_output_tokens += result["output_tokens"]

            await session.commit()

        severity_summary = {"high": 0, "medium": 0, "low": 0}
        for r in results:
            sev = r.get("severity", "medium")
            if sev in severity_summary:
                severity_summary[sev] += 1

        logger.info(
            "Episode %d: analyzed %d items, severity: %s",
            episode_id,
            len(results),
            severity_summary,
        )

        return {
            "items_analyzed": len(results),
            "results": results,
            "severity_summary": severity_summary,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        }

    async def _analyze_item(
        self,
        item: NewsItem,
        provider,
        model: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict:
        """Analyze a single news item."""
        # Include fact-check results in the prompt
        fact_check_info = ""
        if item.fact_check_status:
            fact_check_info = (
                f"\n\nファクトチェック結果:\n"
                f"- ステータス: {item.fact_check_status}\n"
                f"- スコア: {item.fact_check_score}/5\n"
                f"- 詳細: {item.fact_check_details or '(なし)'}"
            )

        prompt = (
            f"タイトル: {item.title}\n"
            f"ソース: {item.source_name}\n"
            f"URL: {item.source_url}\n"
            f"要約: {item.summary or '(なし)'}"
            f"{fact_check_info}"
        )

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=ANALYSIS_SYSTEM_PROMPT,
        )

        data = parse_json_response(response.content)

        # Update the NewsItem in DB
        item.analysis_data = data

        # Record API usage
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
            "severity": data.get("severity", "medium"),
            "topics": data.get("topics", []),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }
