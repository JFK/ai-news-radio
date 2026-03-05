"""RKK Kumamoto Broadcasting scraper (via TBS News Dig)."""

import logging

import httpx
from bs4 import BeautifulSoup, Tag

from app.services.scrapers.base import BaseScraper, ScrapedArticle, ScrapeResult

logger = logging.getLogger(__name__)

# rkk.jp/news/ redirects to TBS News Dig
NEWS_URL = "https://newsdig.tbs.co.jp/list/rkk"


class RKKScraper(BaseScraper):
    """Scraper for RKK Kumamoto Broadcasting via TBS News Dig."""

    @property
    def source_name(self) -> str:
        return "RKK熊本放送"

    @property
    def base_url(self) -> str:
        return "https://newsdig.tbs.co.jp"

    async def scrape(self, client: httpx.AsyncClient) -> ScrapeResult:
        """Fetch and parse TBS News Dig RKK page."""
        try:
            resp = await client.get(NEWS_URL, timeout=15.0)
            resp.raise_for_status()
            articles = self._parse_html(resp.text)
            return ScrapeResult(source_name=self.source_name, articles=articles)
        except Exception as e:
            logger.warning("RKK scrape failed: %s", e)
            return ScrapeResult(source_name=self.source_name, error=str(e))

    def _parse_html(self, html: str) -> list[ScrapedArticle]:
        """Parse TBS News Dig HTML for RKK articles."""
        soup = BeautifulSoup(html, "html.parser")
        articles: list[ScrapedArticle] = []
        seen_urls: set[str] = set()

        for link_tag in soup.select("a[href*='/articles/rkk/']"):
            if not isinstance(link_tag, Tag):
                continue
            href = link_tag.get("href", "")
            if not isinstance(href, str):
                continue

            # Extract clean URL (remove query params like ?display=1)
            clean_href = href.split("?")[0]
            url = f"{self.base_url}{clean_href}" if clean_href.startswith("/") else clean_href

            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Title from .newsCard__title or direct text
            title_el = link_tag.select_one(".newsCard__title")
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
