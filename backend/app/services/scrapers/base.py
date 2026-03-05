"""Base classes for news scrapers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import httpx


@dataclass(frozen=True)
class ScrapedArticle:
    """A single scraped news article."""

    title: str
    url: str
    source_name: str
    summary: str | None = None
    published_at: datetime | None = None


@dataclass
class ScrapeResult:
    """Result from a single scraper run."""

    source_name: str
    articles: list[ScrapedArticle] = field(default_factory=list)
    error: str | None = None


class BaseScraper(ABC):
    """Abstract base class for news scrapers."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of the news source."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL of the news source."""
        ...

    @abstractmethod
    async def scrape(self, client: httpx.AsyncClient) -> ScrapeResult:
        """Scrape articles from the news source.

        Args:
            client: Shared httpx async client for connection pooling.

        Returns:
            ScrapeResult with articles or error information.
        """
        ...
