"""Step 1: News collection pipeline step."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import NewsItem, StepName
from app.pipeline.base import BaseStep

logger = logging.getLogger(__name__)


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
            articles = await self._collect_brave(queries=queries)
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

        logger.info(
            "Episode %d [%s]: found %d articles, saved %d new",
            episode_id,
            method,
            len(articles),
            articles_saved,
        )

        return {
            "collection_method": method,
            "articles_found": len(articles),
            "articles_saved": articles_saved,
            "articles": articles_list,
        }

    async def _collect_brave(self, queries: list[str] | None = None) -> list[dict]:
        """Collect news using Brave Search API."""
        from app.services.brave_search import BraveSearchService

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

        return all_articles
