"""Step 1: News collection pipeline step."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import NewsItem, StepName
from app.pipeline.base import BaseStep
from app.services.prompt_loader import register_default

logger = logging.getLogger(__name__)

RESEARCH_PLAN_PROMPT_KEY = "collection_research_plan"
RESEARCH_INTEGRATE_PROMPT_KEY = "collection_research_integrate"

RESEARCH_PLAN_SYSTEM_PROMPT = """\
あなたはニュースのファクトチェックと調査を行う専門家です。

以下のニュース記事群を読み、検証が必要なクレームや主張を特定してください。
また、追加調査のための検索クエリを3〜5件生成してください。

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "claims_to_verify": [
    {
      "article_index": 0,
      "claim": "検証が必要な主張",
      "reason": "なぜ検証が必要か"
    }
  ],
  "search_queries": ["検索クエリ1", "検索クエリ2", "検索クエリ3"]
}"""

RESEARCH_INTEGRATE_SYSTEM_PROMPT = """\
あなたはニュースのファクトチェックを行う専門家です。

元のニュース記事と追加調査で得られた情報を統合し、各記事のファクトチェック結果を生成してください。

以下のJSON形式で回答してください。JSON以外のテキストは含めないでください:
{
  "results": [
    {
      "article_index": 0,
      "fact_check_status": "verified/partially_verified/unverified/disputed",
      "fact_check_score": 1〜5の整数,
      "fact_check_details": "検証結果の詳細説明",
      "reference_urls": ["参考URL"],
      "key_claims": [
        {
          "claim": "主張",
          "assessment": "confirmed/unconfirmed/disputed",
          "evidence": "根拠"
        }
      ]
    }
  ]
}"""

register_default(RESEARCH_PLAN_PROMPT_KEY, RESEARCH_PLAN_SYSTEM_PROMPT)
register_default(RESEARCH_INTEGRATE_PROMPT_KEY, RESEARCH_INTEGRATE_SYSTEM_PROMPT)


class CollectorStep(BaseStep):
    """Collect news articles from configured sources."""

    @property
    def step_name(self) -> StepName:
        return StepName.COLLECTION

    async def execute(self, episode_id: int, input_data: dict, session: AsyncSession, **kwargs) -> dict:
        """Collect news articles using Brave Search API.

        kwargs:
            queries: Optional list of search queries (overrides settings)

        Idempotent: re-running skips articles whose URL already exists for the episode.
        """
        method = settings.collection_method
        queries = kwargs.get("queries")

        if method == "brave":
            articles = await self._collect_brave(session, episode_id, queries=queries)
        else:
            raise ValueError(f"Unknown collection method: {method}")

        articles_saved = 0
        articles_list: list[dict] = []

        result = await session.execute(select(NewsItem.source_url).where(NewsItem.episode_id == episode_id))
        existing_urls = {row[0] for row in result.all()}

        for article in articles:
            if article["url"] in existing_urls:
                continue

            news_item = NewsItem(
                episode_id=episode_id,
                title=article["title"],
                summary=article.get("summary"),
                source_url=article["url"],
                source_name=article["source_name"],
            )
            session.add(news_item)
            existing_urls.add(article["url"])
            articles_saved += 1
            articles_list.append(article)

        await session.commit()

        # Enrich articles with full body text (also retries items with body=None on re-run)
        enrichment_stats = await self._enrich_articles(episode_id, session)

        # AI multi-stage research (opt-in)
        ai_research_done = False
        if settings.collection_ai_research_enabled:
            ai_research_done = await self._ai_research(episode_id, session)

        logger.info(
            "Episode %d [%s]: found %d articles, saved %d new, enrichment=%s",
            episode_id,
            method,
            len(articles),
            articles_saved,
            enrichment_stats,
        )

        output: dict = {
            "collection_method": method,
            "articles_found": len(articles),
            "articles_saved": articles_saved,
            "articles": articles_list,
            "enrichment": enrichment_stats,
        }
        if ai_research_done:
            output["factcheck_included"] = True
        return output

    async def _collect_brave(
        self, session: AsyncSession, episode_id: int, queries: list[str] | None = None
    ) -> list[dict]:
        """Collect news using Brave Search API."""
        from app.services.brave_search import BRAVE_COST_PER_QUERY, BraveSearchService

        service = BraveSearchService()
        if not queries:
            queries = [q.strip() for q in settings.collection_queries.split(",") if q.strip()]

        all_articles: list[dict] = []
        seen_urls: set[str] = set()

        for query in queries:
            results = await service.web_search(query, count=10, freshness="pw")
            for result in results:
                if result.url in seen_urls:
                    continue
                seen_urls.add(result.url)
                all_articles.append(
                    {
                        "title": result.title,
                        "url": result.url,
                        "summary": result.description,
                        "source_name": f"Brave Search ({query})",
                    }
                )

        # Record Brave Search API usage
        if service.query_count > 0:
            await self.record_usage(
                session=session,
                episode_id=episode_id,
                provider="brave",
                model="brave-search",
                input_tokens=service.query_count,
                output_tokens=0,
                cost_usd=service.query_count * BRAVE_COST_PER_QUERY,
            )

        return all_articles

    async def _enrich_articles(self, episode_id: int, session: AsyncSession) -> dict:
        """Enrich news items with full body text from various sources.

        Dispatches to YouTube transcript, document parser, or web crawler based on URL.
        """
        items = await self._get_news_items(episode_id, session)
        if not items:
            return {"crawled": 0, "youtube": 0, "documents": 0, "errors": 0}

        stats = {"crawled": 0, "youtube": 0, "documents": 0, "errors": 0}

        # Lazy-init services outside the loop
        yt_svc = None
        doc_svc = None
        crawl_svc = None

        for item in items:
            if item.body:
                continue  # Already enriched (idempotent)

            try:
                # YouTube URL → transcript
                if settings.collection_youtube_enabled:
                    from app.services.youtube_transcript import YouTubeTranscriptService

                    if YouTubeTranscriptService.is_youtube_url(item.source_url):
                        if yt_svc is None:
                            yt_svc = YouTubeTranscriptService()
                        result = await yt_svc.get_transcript(item.source_url)
                        if result.success:
                            item.body = result.text
                            stats["youtube"] += 1
                        else:
                            logger.warning("YouTube transcript failed for %s: %s", item.source_url, result.error)
                            stats["errors"] += 1
                        continue

                # Document URL → parse
                if settings.collection_document_enabled:
                    from app.services.document_parser import DocumentParserService

                    if DocumentParserService.is_document_url(item.source_url):
                        if doc_svc is None:
                            doc_svc = DocumentParserService()
                        result = await doc_svc.download_and_parse(item.source_url)
                        if result.success:
                            item.body = result.text
                            stats["documents"] += 1
                        else:
                            logger.warning("Document parse failed for %s: %s", item.source_url, result.error)
                            stats["errors"] += 1
                        continue

                # Default → web crawl
                if settings.collection_crawl_enabled:
                    if crawl_svc is None:
                        from app.services.web_crawler import WebCrawlerService

                        crawl_svc = WebCrawlerService()
                    result = await crawl_svc.crawl(
                        item.source_url,
                        timeout=settings.collection_crawl_timeout,
                        max_chars=settings.collection_crawl_max_body_chars,
                    )
                    if result.success:
                        item.body = result.body
                        stats["crawled"] += 1
                    else:
                        logger.warning("Web crawl failed for %s: %s", item.source_url, result.error)
                        stats["errors"] += 1

            except Exception as e:
                logger.warning("Enrichment failed for %s: %s", item.source_url, e)
                stats["errors"] += 1

        await session.commit()
        return stats

    async def _ai_research(self, episode_id: int, session: AsyncSession) -> bool:
        """Run AI multi-stage research: generate queries, search, and integrate fact-check results.

        Returns True if research completed and fact-check results were written.
        """
        from app.pipeline.utils import parse_json_response
        from app.services.ai_provider import get_provider, get_step_provider
        from app.services.prompt_loader import get_active_prompt

        items = await self._get_news_items(episode_id, session)
        if not items:
            return False

        # Determine provider/model
        if settings.collection_ai_research_provider and settings.collection_ai_research_model:
            provider = get_provider(settings.collection_ai_research_provider)
            model = settings.collection_ai_research_model
        else:
            provider, model = get_step_provider("factcheck")

        # --- Pass 1: Research plan ---
        plan_prompt, _ = await get_active_prompt(session, RESEARCH_PLAN_PROMPT_KEY)

        articles_text = ""
        for i, item in enumerate(items):
            body_excerpt = ""
            if item.body:
                body_excerpt = f"\n  本文冒頭: {item.body[:500]}"
            articles_text += (
                f"\n[{i}] タイトル: {item.title}\n"
                f"  ソース: {item.source_name}\n"
                f"  要約: {item.summary or '(なし)'}"
                f"{body_excerpt}\n"
            )

        response = await provider.generate(
            prompt=f"以下のニュース記事を分析してください:\n{articles_text}",
            model=model,
            system=plan_prompt,
        )
        await self.record_usage(
            session=session, episode_id=episode_id,
            provider=response.provider, model=response.model,
            input_tokens=response.input_tokens, output_tokens=response.output_tokens,
        )

        try:
            plan_data = parse_json_response(response.content)
        except Exception:
            logger.warning("Episode %d: AI research plan returned invalid JSON", episode_id)
            return False

        search_queries = plan_data.get("search_queries", [])
        if not search_queries:
            return False

        # --- Pass 2: Additional search ---
        from app.services.brave_search import BRAVE_COST_PER_QUERY, BraveSearchService

        additional_info = ""
        brave_query_count = 0
        max_rounds = settings.collection_ai_research_max_rounds
        for round_num in range(max_rounds):
            if round_num >= len(search_queries):
                break
            batch = search_queries[round_num * 3 : (round_num + 1) * 3]
            for query in batch:
                try:
                    search_svc = BraveSearchService()
                    results = await search_svc.web_search(query, count=5)
                    brave_query_count += 1
                    for r in results:
                        additional_info += f"\n- [{query}] {r.title}: {r.description}\n  URL: {r.url}"

                        # Crawl additional results for deeper info
                        if settings.collection_crawl_enabled:
                            from app.services.web_crawler import WebCrawlerService

                            crawler = WebCrawlerService()
                            crawl_result = await crawler.crawl(
                                r.url,
                                timeout=settings.collection_crawl_timeout,
                                max_chars=5000,
                            )
                            if crawl_result.success and crawl_result.body:
                                additional_info += f"\n  本文: {crawl_result.body[:2000]}"
                except Exception as e:
                    logger.warning("Additional search failed for '%s': %s", query, e)

        # Record Brave Search API usage for research queries
        if brave_query_count > 0:
            await self.record_usage(
                session=session,
                episode_id=episode_id,
                provider="brave",
                model="brave-search",
                input_tokens=brave_query_count,
                output_tokens=0,
                cost_usd=brave_query_count * BRAVE_COST_PER_QUERY,
            )

        if not additional_info:
            return False

        # --- Pass 3: Integration ---
        integrate_prompt, _ = await get_active_prompt(session, RESEARCH_INTEGRATE_PROMPT_KEY)

        integrate_input = (
            f"元の記事:\n{articles_text}\n\n"
            f"追加調査結果:\n{additional_info}"
        )

        response = await provider.generate(
            prompt=integrate_input,
            model=model,
            system=integrate_prompt,
        )
        await self.record_usage(
            session=session, episode_id=episode_id,
            provider=response.provider, model=response.model,
            input_tokens=response.input_tokens, output_tokens=response.output_tokens,
        )

        try:
            integrate_data = parse_json_response(response.content)
        except Exception:
            logger.warning("Episode %d: AI research integration returned invalid JSON", episode_id)
            return False

        # Write fact-check results to NewsItems
        results_list = integrate_data.get("results", [])
        for fc_result in results_list:
            idx = fc_result.get("article_index")
            if idx is not None and 0 <= idx < len(items):
                item = items[idx]
                item.fact_check_status = fc_result.get("fact_check_status", "unverified")
                item.fact_check_score = fc_result.get("fact_check_score", 1)
                item.fact_check_details = fc_result.get("fact_check_details", "")
                item.reference_urls = fc_result.get("reference_urls", [])

        await session.commit()

        logger.info(
            "Episode %d: AI research completed, %d items fact-checked",
            episode_id,
            len(results_list),
        )
        return True
