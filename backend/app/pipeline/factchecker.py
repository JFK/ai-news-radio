"""Step 2: Fact-checking pipeline step."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewsItem, StepName
from app.pipeline.base import BaseStep
from app.pipeline.utils import parse_json_response
from app.services.ai_provider import get_step_provider
from app.services.prompt_loader import get_active_prompt, register_default

logger = logging.getLogger(__name__)

PROMPT_KEY = "factcheck"

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

register_default(PROMPT_KEY, FACTCHECK_SYSTEM_PROMPT)


class FactcheckerStep(BaseStep):
    """Fact-check news articles using AI."""

    @property
    def step_name(self) -> StepName:
        return StepName.FACTCHECK

    async def execute(self, episode_id: int, input_data: dict, session: AsyncSession, **kwargs) -> dict:
        """Fact-check each NewsItem for the episode.

        If the collection step already performed AI research (factcheck_included=True),
        skip AI calls and return the pre-populated fact-check data.

        One AI call per article for quality, cost management, and error isolation.
        Idempotent: re-running overwrites previous results.
        """
        # Skip path: collection AI research already did fact-checking
        if input_data.get("factcheck_included"):
            items = await self._get_news_items(episode_id, session)
            results = []
            for item in items:
                results.append({
                    "news_item_id": item.id,
                    "title": item.title,
                    "status": item.fact_check_status or "unverified",
                    "score": item.fact_check_score or 1,
                    "input_tokens": 0,
                    "output_tokens": 0,
                })
            avg_score = sum(r["score"] for r in results) / len(results) if results else 0
            return {
                "items_checked": len(results),
                "results": results,
                "average_score": round(avg_score, 2),
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "factcheck_source": "collection_ai_research",
            }

        provider, model = get_step_provider(self.step_name.value)
        system_prompt, prompt_version = await get_active_prompt(session, PROMPT_KEY)
        results: list[dict] = []
        total_input_tokens = 0
        total_output_tokens = 0

        items = await self._get_news_items(episode_id, session)

        for item in items:
            result = await self._check_item(item, provider, model, system_prompt, session, episode_id)
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

        result_data: dict = {
            "items_checked": len(results),
            "results": results,
            "average_score": round(avg_score, 2),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        }
        if prompt_version is not None:
            result_data["prompt_version"] = prompt_version
        return result_data

    async def _search_references(
        self, item: NewsItem, session: AsyncSession, episode_id: int
    ) -> str:
        """Search for reference material using Brave Search (if available)."""
        try:
            from app.config import settings

            if not settings.brave_search_api_key:
                return ""

            from app.services.brave_search import BRAVE_COST_PER_QUERY, BraveSearchService

            service = BraveSearchService()
            results = await service.web_search(item.title, count=5)

            # Record Brave Search API usage
            await self.record_usage(
                session=session,
                episode_id=episode_id,
                provider="brave",
                model="brave-search",
                input_tokens=1,
                output_tokens=0,
                cost_usd=BRAVE_COST_PER_QUERY,
            )

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
        system_prompt: str,
        session: AsyncSession,
        episode_id: int,
    ) -> dict:
        """Fact-check a single news item."""
        # Search for reference material
        search_context = await self._search_references(item, session, episode_id)

        body_excerpt = ""
        if item.body:
            body_excerpt = f"\n本文（冒頭5000字）:\n{item.body[:5000]}"

        prompt = (
            f"タイトル: {item.title}\n"
            f"ソース: {item.source_name}\n"
            f"URL: {item.source_url}\n"
            f"要約: {item.summary or '(なし)'}"
            f"{body_excerpt}"
            f"{search_context}"
        )

        response = await provider.generate(
            prompt=prompt,
            model=model,
            system=system_prompt,
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
