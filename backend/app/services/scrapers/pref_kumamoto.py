"""Kumamoto Prefecture official website scraper (RSS 1.0 / RDF)."""

import logging
from datetime import datetime
from xml.etree.ElementTree import fromstring

import httpx

from app.services.scrapers.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

RSS_URL = "https://www.pref.kumamoto.jp/rss/10/list3.xml"

# RDF/RSS 1.0 namespaces
_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rss": "http://purl.org/rss/1.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class PrefKumamotoScraper(BaseScraper):
    """Scraper for Kumamoto Prefecture official RSS feed (RDF 1.0)."""

    @property
    def source_name(self) -> str:
        return "熊本県公式"

    @property
    def base_url(self) -> str:
        return "https://www.pref.kumamoto.jp"

    async def scrape(self, client: httpx.AsyncClient) -> ScrapeResult:
        """Fetch and parse Kumamoto Prefecture RSS feed."""
        try:
            resp = await client.get(RSS_URL, timeout=15.0)
            resp.raise_for_status()
            articles = self._parse_rss(resp.text)
            return ScrapeResult(source_name=self.source_name, articles=articles)
        except Exception as e:
            logger.warning("Pref Kumamoto scrape failed: %s", e)
            return ScrapeResult(source_name=self.source_name, error=str(e))

    def _parse_rss(self, xml_text: str) -> list[ScrapedArticle]:
        """Parse RSS 1.0 (RDF) XML into ScrapedArticle list."""
        root = fromstring(xml_text)
        articles: list[ScrapedArticle] = []

        for item in root.findall("rss:item", _NS):
            title_el = item.find("rss:title", _NS)
            link_el = item.find("rss:link", _NS)
            if title_el is None or link_el is None:
                continue
            title = title_el.text
            link = link_el.text
            if not title or not link:
                continue

            desc_el = item.find("rss:description", _NS)
            description = desc_el.text if desc_el is not None and desc_el.text else None

            date_el = item.find("dc:date", _NS)
            published_at = _parse_iso_date(date_el.text) if date_el is not None and date_el.text else None

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


def _parse_iso_date(date_str: str) -> datetime | None:
    """Parse ISO 8601 date string (with timezone)."""
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None
