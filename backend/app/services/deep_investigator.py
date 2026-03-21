"""Deep investigation service for multi-round research.

Performs agent-style iterative research:
1. Plan — identify knowledge gaps and generate queries
2. Search — Web + Academic + targeted URL crawling
3. Analyze — integrate findings, identify remaining gaps
4. Repeat until budget exhausted or gaps filled
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.ai_provider import AIResponse, get_provider, get_step_provider
from app.services.cost_estimator import estimate_cost

logger = logging.getLogger(__name__)

# Type for the cost recording callback
RecordUsageFn = Callable[..., Awaitable[None]]

INVESTIGATION_PLAN_PROMPT = """\
あなたは調査ジャーナリストです。以下のニュース記事を読み、深層調査を計画してください。

記事の内容を分析し、以下を特定してください:
1. まだ不明な点・未検証の主張
2. より深い理解に必要な背景情報
3. 関連する統計データや公的資料
4. 異なる視点や反論

以下のJSON形式で回答してください:
{
  "knowledge_gaps": [
    {"topic": "不明な点", "importance": "high/medium/low", "type": "fact/context/data/perspective"}
  ],
  "search_queries": {
    "web": ["Web検索クエリ1", "Web検索クエリ2"],
    "academic": ["学術検索クエリ1"],
    "urls_to_crawl": ["https://specific-url-to-check.example.com"]
  },
  "reasoning": "調査計画の根拠"
}"""

INVESTIGATION_INTEGRATE_PROMPT = """\
あなたは調査ジャーナリストです。これまでの調査結果を統合し、残る知識ギャップを評価してください。

以下のJSON形式で回答してください:
{
  "findings": [
    {
      "topic": "発見したこと",
      "summary": "要約",
      "confidence": "high/medium/low",
      "sources": ["URL1", "URL2"]
    }
  ],
  "remaining_gaps": [
    {"topic": "まだ不明な点", "importance": "high/medium/low"}
  ],
  "additional_queries": {
    "web": ["追加Web検索クエリ"],
    "academic": ["追加学術検索クエリ"]
  },
  "should_continue": true,
  "summary": "調査のサマリー"
}"""

INVESTIGATION_FINAL_PROMPT = """\
あなたは調査ジャーナリストです。深層調査の全結果を構造化されたリサーチサマリーにまとめてください。

以下のJSON形式で回答してください:
{
  "executive_summary": "調査の概要（3-5文）",
  "key_findings": [
    {
      "finding": "重要な発見",
      "confidence": "high/medium/low",
      "evidence": "根拠",
      "sources": ["URL"]
    }
  ],
  "unresolved_questions": ["未解決の疑問"],
  "fact_check_updates": [
    {
      "article_index": 0,
      "fact_check_status": "verified/partially_verified/unverified/disputed",
      "fact_check_score": 1-5,
      "fact_check_details": "検証結果",
      "reference_urls": ["URL"]
    }
  ],
  "total_sources_consulted": 0
}"""


@dataclass
class InvestigationRound:
    """Record of a single investigation round."""

    round_num: int
    queries_executed: list[str] = field(default_factory=list)
    findings_count: int = 0
    remaining_gaps: int = 0
    cost_usd: float = 0.0


@dataclass
class InvestigationResult:
    """Result of deep investigation."""

    success: bool
    summary: str
    rounds: list[InvestigationRound] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    fact_check_updates: list[dict] = field(default_factory=list)
    total_cost_usd: float = 0.0
    error: str | None = None


class DeepInvestigator:
    """Multi-round deep investigation engine."""

    def __init__(
        self,
        session: AsyncSession,
        episode_id: int,
        record_usage_fn: RecordUsageFn | None = None,
    ) -> None:
        self._session = session
        self._episode_id = episode_id
        self._record_usage_fn = record_usage_fn
        self._research_notes: list[str] = []
        self._total_cost_usd: float = 0.0

    async def investigate(
        self,
        articles_text: str,
        max_rounds: int | None = None,
        max_cost_usd: float | None = None,
    ) -> InvestigationResult:
        """Run multi-round deep investigation.

        Args:
            articles_text: Formatted text of news articles.
            max_rounds: Maximum investigation rounds (defaults to settings).
            max_cost_usd: Cost budget in USD (defaults to settings).

        Returns:
            InvestigationResult with findings and fact-check updates.
        """
        max_rounds = max_rounds or settings.collection_deep_investigation_max_rounds
        max_cost_usd = max_cost_usd or settings.collection_deep_investigation_max_cost_usd

        provider, model = self._get_provider_and_model()
        rounds: list[InvestigationRound] = []

        # Overall timeout: 5 min per round max
        overall_timeout = max_rounds * 300

        try:
            async with asyncio.timeout(overall_timeout):
                for round_num in range(max_rounds):
                    if self._total_cost_usd >= max_cost_usd:
                        logger.info(
                            "Episode %d: Deep investigation stopped at round %d (cost limit: $%.4f)",
                            self._episode_id,
                            round_num,
                            self._total_cost_usd,
                        )
                        break

                    round_result = await self._run_round(round_num, articles_text, provider, model, max_cost_usd)
                    rounds.append(round_result)

                    # Check if AI thinks we should stop
                    if round_num > 0 and round_result.remaining_gaps == 0:
                        break

                # Final synthesis
                final_result = await self._synthesize(articles_text, provider, model)

            return InvestigationResult(
                success=True,
                summary=final_result.get("executive_summary", ""),
                rounds=rounds,
                findings=final_result.get("key_findings", []),
                fact_check_updates=final_result.get("fact_check_updates", []),
                total_cost_usd=self._total_cost_usd,
            )
        except TimeoutError:
            logger.warning(
                "Episode %d: Deep investigation timed out after %ds (%d rounds completed)",
                self._episode_id,
                overall_timeout,
                len(rounds),
            )
            # Return partial results on timeout
            return InvestigationResult(
                success=True,
                summary=f"調査はタイムアウトしましたが、{len(rounds)}ラウンドの部分結果を返します。",
                rounds=rounds,
                total_cost_usd=self._total_cost_usd,
            )
        except Exception as e:
            logger.exception("Episode %d: Deep investigation failed", self._episode_id)
            return InvestigationResult(
                success=False,
                summary="",
                rounds=rounds,
                total_cost_usd=self._total_cost_usd,
                error=str(e),
            )

    async def _run_round(
        self,
        round_num: int,
        articles_text: str,
        provider,
        model: str,
        max_cost_usd: float,
    ) -> InvestigationRound:
        """Execute a single investigation round."""
        from app.pipeline.utils import parse_json_response

        round_record = InvestigationRound(round_num=round_num)

        # Step 1: Plan (or re-plan with accumulated notes)
        if round_num == 0:
            plan_prompt = f"以下のニュース記事を分析してください:\n{articles_text}"
            system = INVESTIGATION_PLAN_PROMPT
        else:
            plan_prompt = (
                f"以下のニュース記事:\n{articles_text}\n\n"
                f"これまでの調査メモ:\n{''.join(self._research_notes)}\n\n"
                "残る知識ギャップを特定し、追加調査を計画してください。"
            )
            system = INVESTIGATION_INTEGRATE_PROMPT

        response = await provider.generate(prompt=plan_prompt, model=model, system=system)
        await self._record_and_track(response)

        try:
            plan_data = parse_json_response(response.content)
        except Exception:
            logger.warning("Episode %d: Round %d plan returned invalid JSON", self._episode_id, round_num)
            return round_record

        # Step 2: Execute searches
        search_queries = plan_data.get("search_queries") or plan_data.get("additional_queries", {})
        web_queries = search_queries.get("web", [])
        academic_queries = search_queries.get("academic", [])
        urls_to_crawl = search_queries.get("urls_to_crawl", [])

        search_results = ""

        # Web search
        if web_queries and self._total_cost_usd < max_cost_usd:
            search_results += await self._web_search(web_queries[:3])
            round_record.queries_executed.extend(web_queries[:3])

        # Academic search
        if academic_queries and settings.collection_academic_search_enabled and self._total_cost_usd < max_cost_usd:
            search_results += await self._academic_search(academic_queries[:2])
            round_record.queries_executed.extend(academic_queries[:2])

        # Targeted URL crawling
        if urls_to_crawl and settings.collection_crawl_enabled and self._total_cost_usd < max_cost_usd:
            search_results += await self._crawl_urls(urls_to_crawl[:3])

        if search_results:
            self._research_notes.append(f"\n--- Round {round_num + 1} ---\n{search_results}")

        # Step 3: Analyze round results
        if round_num > 0 and search_results:
            integrate_response = await provider.generate(
                prompt=(
                    f"元の記事:\n{articles_text}\n\n"
                    f"今回の調査結果:\n{search_results}\n\n"
                    f"累積調査メモ:\n{''.join(self._research_notes)}"
                ),
                model=model,
                system=INVESTIGATION_INTEGRATE_PROMPT,
            )
            await self._record_and_track(integrate_response)

            try:
                integrate_data = parse_json_response(integrate_response.content)
                round_record.findings_count = len(integrate_data.get("findings", []))
                round_record.remaining_gaps = len(integrate_data.get("remaining_gaps", []))
            except Exception:
                pass

        round_record.cost_usd = self._total_cost_usd
        return round_record

    async def _synthesize(self, articles_text: str, provider, model: str) -> dict:
        """Final synthesis of all research notes."""
        from app.pipeline.utils import parse_json_response

        response = await provider.generate(
            prompt=(
                f"元のニュース記事:\n{articles_text}\n\n"
                f"全調査メモ:\n{''.join(self._research_notes)}\n\n"
                "これらの調査結果を最終レポートにまとめてください。"
            ),
            model=model,
            system=INVESTIGATION_FINAL_PROMPT,
        )
        await self._record_and_track(response)

        try:
            return parse_json_response(response.content)
        except Exception:
            logger.warning("Episode %d: Final synthesis returned invalid JSON", self._episode_id)
            return {"executive_summary": response.content}

    async def _web_search(self, queries: list[str]) -> str:
        """Execute web searches and crawl top results for deeper info."""
        from app.services.brave_search import BraveSearchService

        results_text = ""
        crawler = None
        max_crawl_per_query = 2  # Limit crawls to avoid timeout

        for query in queries:
            try:
                search_svc = BraveSearchService()
                results = await search_svc.web_search(query, count=5)
                crawled = 0
                for r in results:
                    results_text += f"\n[Web: {query}] {r.title}: {r.description}\n  URL: {r.url}"

                    # Crawl top N results only for deeper info
                    if settings.collection_crawl_enabled and crawled < max_crawl_per_query:
                        if crawler is None:
                            from app.services.web_crawler import WebCrawlerService

                            crawler = WebCrawlerService()
                        try:
                            crawl_result = await asyncio.wait_for(
                                crawler.crawl(r.url, timeout=10.0, max_chars=3000),
                                timeout=15.0,
                            )
                            if crawl_result.success and crawl_result.body:
                                results_text += f"\n  本文: {crawl_result.body[:1500]}"
                                crawled += 1
                        except TimeoutError:
                            logger.debug("Deep investigation crawl timed out for %s", r.url)
            except Exception as e:
                logger.warning("Deep investigation web search failed for '%s': %s", query, e)
        return results_text

    async def _academic_search(self, queries: list[str]) -> str:
        """Execute academic paper searches."""
        from app.services.academic_search import AcademicSearchService

        results_text = ""
        svc = AcademicSearchService()
        for query in queries:
            try:
                result = await svc.search(query, max_results=3)
                for paper in result.papers:
                    results_text += (
                        f"\n[Academic: {query}] {paper.title}"
                        f"\n  著者: {', '.join(paper.authors[:3])}"
                        f"\n  年: {paper.year or 'N/A'}"
                        f"\n  要旨: {paper.abstract[:500]}"
                        f"\n  URL: {paper.url}"
                    )

            except Exception as e:
                logger.warning("Deep investigation academic search failed for '%s': %s", query, e)
        return results_text

    async def _crawl_urls(self, urls: list[str]) -> str:
        """Crawl specific URLs for information."""
        from app.services.web_crawler import WebCrawlerService

        results_text = ""
        crawler = WebCrawlerService()
        for url in urls:
            try:
                crawl_result = await asyncio.wait_for(
                    crawler.crawl(url, timeout=10.0, max_chars=5000),
                    timeout=15.0,
                )
                if crawl_result.success and crawl_result.body:
                    results_text += f"\n[Crawl: {url}]\n{crawl_result.body[:3000]}"
            except TimeoutError:
                logger.debug("Deep investigation crawl timed out for %s", url)
            except Exception as e:
                logger.warning("Deep investigation crawl failed for '%s': %s", url, e)
        return results_text

    async def _record_and_track(self, response: AIResponse) -> None:
        """Record API usage to DB and track cumulative cost."""
        cost = await estimate_cost(self._session, response.model, response.input_tokens, response.output_tokens)
        self._total_cost_usd += cost

        if self._record_usage_fn:
            await self._record_usage_fn(
                session=self._session,
                episode_id=self._episode_id,
                provider=response.provider,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=cost,
            )

    @staticmethod
    def _get_provider_and_model():
        """Get provider and model for deep investigation."""
        if settings.collection_deep_investigation_provider and settings.collection_deep_investigation_model:
            provider = get_provider(settings.collection_deep_investigation_provider)
            model = settings.collection_deep_investigation_model
            return provider, model
        return get_step_provider("factcheck")
