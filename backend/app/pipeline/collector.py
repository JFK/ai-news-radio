"""Step 1: News collection pipeline step."""

import logging

from sqlalchemy import select

from app.database import async_session
from app.models import NewsItem, StepName
from app.pipeline.base import BaseStep
from app.services.scraper import ScraperService

logger = logging.getLogger(__name__)


class CollectorStep(BaseStep):
    """Collect news articles from configured sources."""

    @property
    def step_name(self) -> StepName:
        return StepName.COLLECTION

    async def execute(self, episode_id: int, input_data: dict) -> dict:
        """Scrape news sources and create NewsItem records.

        Idempotent: re-running skips articles whose URL already exists for the episode.

        Returns:
            dict with articles_found, articles_saved, and articles list.
        """
        service = ScraperService()
        scraped = await service.collect_all()

        articles_saved = 0
        articles_list: list[dict] = []

        async with async_session() as session:
            # Get existing URLs for this episode to ensure idempotency
            result = await session.execute(select(NewsItem.source_url).where(NewsItem.episode_id == episode_id))
            existing_urls = {row[0] for row in result.all()}

            for article in scraped:
                if article.url in existing_urls:
                    continue

                news_item = NewsItem(
                    episode_id=episode_id,
                    title=article.title,
                    summary=article.summary,
                    source_url=article.url,
                    source_name=article.source_name,
                )
                session.add(news_item)
                existing_urls.add(article.url)
                articles_saved += 1

                articles_list.append(
                    {
                        "title": article.title,
                        "url": article.url,
                        "source_name": article.source_name,
                        "summary": article.summary,
                        "published_at": article.published_at.isoformat() if article.published_at else None,
                    }
                )

            await session.commit()

        logger.info(
            "Episode %d: found %d articles, saved %d new",
            episode_id,
            len(scraped),
            articles_saved,
        )

        return {
            "articles_found": len(scraped),
            "articles_saved": articles_saved,
            "articles": articles_list,
        }
