"""NHK Kumamoto news scraper (RSS feed)."""

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree.ElementTree import Element, fromstring

import httpx

from app.services.scrapers.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

RSS_URL = "https://www3.nhk.or.jp/lnews/kumamoto/rss.xml"


class NHKKumamotoScraper(BaseScraper):
    """Scraper for NHK Kumamoto using RSS feed."""

    @property
    def source_name(self) -> str:
        return "NHK熊本"

    @property
    def base_url(self) -> str:
        return "https://www3.nhk.or.jp/lnews/kumamoto/"

    async def scrape(self, client: httpx.AsyncClient) -> ScrapeResult:
        """Fetch and parse NHK Kumamoto RSS feed."""
        try:
            resp = await client.get(RSS_URL, timeout=15.0)
            resp.raise_for_status()
            articles = self._parse_rss(resp.text)
            return ScrapeResult(source_name=self.source_name, articles=articles)
        except Exception as e:
            logger.warning("NHK Kumamoto scrape failed: %s", e)
            return ScrapeResult(source_name=self.source_name, error=str(e))

    def _parse_rss(self, xml_text: str) -> list[ScrapedArticle]:
        """Parse RSS XML into ScrapedArticle list."""
        root = fromstring(xml_text)
        articles: list[ScrapedArticle] = []

        for item in root.iter("item"):
            title = _text(item, "title")
            link = _text(item, "link")
            if not title or not link:
                continue

            pub_date = _text(item, "pubDate")
            published_at = _parse_rfc2822(pub_date) if pub_date else None
            description = _text(item, "description")

            articles.append(
                ScrapedArticle(
                    title=title.strip(),
                    url=link.strip(),
                    source_name=self.source_name,
                    summary=description.strip() if description else None,
                    published_at=published_at,
                )
            )

        return articles


def _text(element: Element, tag: str) -> str | None:
    """Get text content of a child element."""
    child = element.find(tag)
    return child.text if child is not None and child.text else None


def _parse_rfc2822(date_str: str) -> datetime | None:
    """Parse RFC 2822 date string to timezone-aware datetime."""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(UTC)
    except (ValueError, TypeError):
        return None
