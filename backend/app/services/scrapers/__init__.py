"""News scrapers for various Kumamoto news sources."""

from app.services.scrapers.base import BaseScraper, ScrapedArticle, ScrapeResult
from app.services.scrapers.kab import KABScraper
from app.services.scrapers.nhk_kumamoto import NHKKumamotoScraper
from app.services.scrapers.pref_kumamoto import PrefKumamotoScraper
from app.services.scrapers.rkk import RKKScraper

# NHKKumamotoScraper is excluded: RSS feed now requires JWT authentication.
# Can be re-added via ScraperService.register() if auth becomes available.
DEFAULT_SCRAPERS: list[type[BaseScraper]] = [
    PrefKumamotoScraper,
    RKKScraper,
    KABScraper,
]

__all__ = [
    "DEFAULT_SCRAPERS",
    "BaseScraper",
    "KABScraper",
    "NHKKumamotoScraper",
    "PrefKumamotoScraper",
    "RKKScraper",
    "ScrapedArticle",
    "ScrapeResult",
]
