"""Scraper service that orchestrates all news scrapers."""

import asyncio
import logging
from urllib.parse import urlparse

import httpx

from app.services.scrapers import DEFAULT_SCRAPERS
from app.services.scrapers.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

USER_AGENT = "AINewsRadio/1.0"


class ScraperService:
    """Orchestrates multiple scrapers with parallel execution and deduplication.

    Scrapers can be dynamically added or removed at runtime.
    """

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseScraper]] = {}
        # Register default scrapers
        for cls in DEFAULT_SCRAPERS:
            self.register(cls)

    def register(self, scraper_class: type[BaseScraper]) -> None:
        """Register a scraper. Keyed by source_name."""
        instance = scraper_class()
        self._registry[instance.source_name] = scraper_class

    def unregister(self, source_name: str) -> None:
        """Remove a scraper by source_name."""
        self._registry.pop(source_name, None)

    @property
    def registered_names(self) -> list[str]:
        """List of currently registered scraper source names."""
        return list(self._registry.keys())

    async def collect_all(self) -> list[ScrapedArticle]:
        """Run all registered scrapers in parallel and return deduplicated articles.

        Error isolation: if one scraper fails, others still return results.
        """
        if not self._registry:
            return []

        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            tasks = [cls().scrape(client) for cls in self._registry.values()]
            results: list[ScrapeResult] = await asyncio.gather(*tasks, return_exceptions=False)

        all_articles: list[ScrapedArticle] = []
        for result in results:
            if result.error:
                logger.warning("Scraper %s failed: %s", result.source_name, result.error)
            else:
                logger.info("Scraper %s: %d articles", result.source_name, len(result.articles))
            all_articles.extend(result.articles)

        return _deduplicate(all_articles)


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication.

    - Lowercase scheme and host
    - Remove trailing slash
    - Remove fragment
    """
    parsed = urlparse(url)
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=parsed.path.rstrip("/") or "/",
        fragment="",
    )
    return normalized.geturl()


def _deduplicate(articles: list[ScrapedArticle]) -> list[ScrapedArticle]:
    """Remove duplicate articles based on normalized URL."""
    seen: set[str] = set()
    unique: list[ScrapedArticle] = []
    for article in articles:
        key = _normalize_url(article.url)
        if key not in seen:
            seen.add(key)
            unique.append(article)
    return unique
