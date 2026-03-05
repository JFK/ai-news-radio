"""KAB Kumamoto Asahi Broadcasting scraper (RSS with HTML fallback)."""

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from xml.etree.ElementTree import Element, fromstring

import httpx
from bs4 import BeautifulSoup, Tag

from app.services.scrapers.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

RSS_URL = "https://www.kab.co.jp/rss/"
HTML_URL = "https://www.kab.co.jp/news/"


class KABScraper(BaseScraper):
    """Scraper for KAB Kumamoto Asahi Broadcasting. Tries RSS first, falls back to HTML."""

    @property
    def source_name(self) -> str:
        return "KAB熊本朝日放送"

    @property
    def base_url(self) -> str:
        return "https://www.kab.co.jp"

    async def scrape(self, client: httpx.AsyncClient) -> ScrapeResult:
        """Try RSS feed first, fall back to HTML scraping on failure."""
        # Try RSS first
        try:
            resp = await client.get(RSS_URL, timeout=15.0)
            resp.raise_for_status()
            articles = self._parse_rss(resp.text)
            if articles:
                return ScrapeResult(source_name=self.source_name, articles=articles)
        except Exception as e:
            logger.info("KAB RSS failed, trying HTML fallback: %s", e)

        # Fallback to HTML
        try:
            resp = await client.get(HTML_URL, timeout=15.0)
            resp.raise_for_status()
            articles = self._parse_html(resp.text)
            return ScrapeResult(source_name=self.source_name, articles=articles)
        except Exception as e:
            logger.warning("KAB scrape failed (both RSS and HTML): %s", e)
            return ScrapeResult(source_name=self.source_name, error=str(e))

    def _parse_rss(self, xml_text: str) -> list[ScrapedArticle]:
        """Parse WordPress RSS feed."""
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

    def _parse_html(self, html: str) -> list[ScrapedArticle]:
        """Parse KAB news list HTML as fallback.

        Only matches actual article links (/news/article/DIGITS),
        skipping category pages, series, and navigation.
        """
        import re

        soup = BeautifulSoup(html, "html.parser")
        articles: list[ScrapedArticle] = []
        seen_urls: set[str] = set()

        for link_tag in soup.select("a[href*='/news/article/']"):
            if not isinstance(link_tag, Tag):
                continue
            href = link_tag.get("href", "")
            if not isinstance(href, str):
                continue
            # Strict: only /news/article/<digits>
            if not re.search(r"/news/article/\d+", href):
                continue

            url = urljoin(self.base_url, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Prefer title from h3
            title_el = link_tag.find("h3")
            title = title_el.get_text(strip=True) if title_el else link_tag.get_text(strip=True)
            if not title:
                continue

            articles.append(
                ScrapedArticle(
                    title=title,
                    url=url,
                    source_name=self.source_name,
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
