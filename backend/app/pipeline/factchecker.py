"""Step 2: Fact-checking pipeline step."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import NewsItem, StepName
from app.pipeline.base import BaseStep
from app.pipeline.utils import parse_json_response
from app.services.ai_provider import get_step_provider

logger = logging.getLogger(__name__)

FACTCHECK_SYSTEM_PROMPT = """\
あなたはニュースのファクトチェックを行う専門家です。

与えられたニュース記事に対して、以下の観点でファクトチェックを行ってください:

1. **ソースの信頼性評価**: 情報源は誰か？一次情報か？利害関係はあるか？
2. **事実確認**: 記事中の主要な主張は事実か？確認できるか？
3. **裏取りURL**: 主張を裏付ける、または反論する参考URLがあれば提示
4. **不確実性の明示**: 確認できない情報は「確認できない」と明示

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "fact_check_status": "verified または partially_verified または unverified または disputed",
  "fact_check_score": 1から5の整数（5=複数ソースで確認済み、4=概ね確認、3=一部未確認、2=信頼性に疑問、1=矛盾あり）,
  "fact_check_details": "検証結果の詳細説明",
  "reference_urls": ["参考URL1", "参考URL2"],
  "key_claims": [
    {
      "claim": "記事中の主要な主張",
      "assessment": "confirmed または unconfirmed または disputed",
      "evidence": "判断の根拠"
    }
  ]
}"""


class FactcheckerStep(BaseStep):
    """Fact-check news articles using AI."""

    @property
    def step_name(self) -> StepName:
        return StepName.FACTCHECK

    async def execute(self, episode_id: int, input_data: dict, **kwargs) -> dict:
        """Fact-check each NewsItem for the episode.

        One AI call per article for quality, cost management, and error isolation.
        Idempotent: re-running overwrites previous results.
        """
        provider, model = get_step_provider(self.step_name.value)
        results: list[dict] = []
        total_input_tokens = 0
        total_output_tokens = 0

        async with async_session() as session:
            items = await self._get_news_items(episode_id, session)

            for item in items:
                result = await self._check_item(item, provider, model, session, episode_id)
                results.append(result)
                total_input_tokens += result["input_tokens"]
                total_output_tokens += result["output_tokens"]

            await session.commit()

        avg_score = sum(r["score"] for r in results) / len(results) if results else 0

        logger.info(
            "Episode %d: fact-checked %d items, average score %.1f",
            episode_id,
            len(results),
            avg_score,
        )

        return {
            "items_checked": len(results),
            "results": results,
            "average_score": round(avg_score, 2),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        }

    async def _get_news_items(self, episode_id: int, session: AsyncSession) -> list[NewsItem]:
        """Load all NewsItems for the episode."""
        result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode_id).order_by(NewsItem.id))
        return list(result.scalars().all())

    async def _search_references(self, item: NewsItem) -> str:
        """Search for reference material using Brave Search (if available)."""
        try:
            from app.config import settings

            if not settings.brave_search_api_key:
                return ""

            from app.services.brave_search import BraveSearchService

            service = BraveSearchService()
            results = await service.web_search(item.title, count=5)
            if not results:
                return ""

            lines = ["\n\n参考検索結果（裏取り用）:"]
            for r in results:
                lines.append(f"- {r.title}: {r.url}")
                if r.description:
                    lines.append(f"  {r.description}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("Brave Search for fact-check failed: %s", e)
            return ""

    async def _check_item(
        self,
        item: NewsItem,
        provider,
        model: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict:
        """Fact-check a single news item."""
        # Search for reference material
        search_context = await self._search_references(item)

        prompt = (
            f"タイトル: {item.title}\n"
            f"ソース: {item.source_name}\n"
            f"URL: {item.source_url}\n"
            f"要約: {item.summary or '(なし)'}"
            f"{search_context}"
        )

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=FACTCHECK_SYSTEM_PROMPT,
        )

        data = parse_json_response(response.content)

        # Update the NewsItem in DB
        item.fact_check_status = data.get("fact_check_status", "unverified")
        item.fact_check_score = data.get("fact_check_score", 1)
        item.fact_check_details = data.get("fact_check_details", "")
        item.reference_urls = data.get("reference_urls", [])

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
            "status": item.fact_check_status,
            "score": item.fact_check_score,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }
