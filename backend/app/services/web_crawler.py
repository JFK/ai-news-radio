"""Web crawling service for article body extraction."""

import logging
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REMOVE_TAGS = {"nav", "footer", "aside", "script", "style", "header", "noscript", "iframe", "form"}


@dataclass
class CrawlResult:
    """Result of a web crawl."""

    body: str
    content_type: str
    success: bool
    error: str | None = None


class WebCrawlerService:
    """Crawl web pages and extract article body text."""

    async def crawl(self, url: str, timeout: float = 15.0, max_chars: int = 50000) -> CrawlResult:
        """Crawl a URL and extract the article body text.

        Args:
            url: The URL to crawl.
            timeout: Request timeout in seconds.
            max_chars: Maximum characters to extract.

        Returns:
            CrawlResult with extracted body text or error.
        """
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AINewsRadio/1.0)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return CrawlResult(body="", content_type=content_type, success=False, error=f"Not HTML: {content_type}")

            body = self._extract_text(response.text, max_chars)
            return CrawlResult(body=body, content_type=content_type, success=True)

        except httpx.HTTPStatusError as e:
            return CrawlResult(body="", content_type="", success=False, error=f"HTTP {e.response.status_code}")
        except Exception as e:
            return CrawlResult(body="", content_type="", success=False, error=str(e))

    def _extract_text(self, html: str, max_chars: int) -> str:
        """Extract article text from HTML with fallback strategy.

        Tries <article> → <main> → <body> in order.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove unwanted elements
        for tag_name in REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Try article → main → body
        for selector in ["article", "main", "body"]:
            element = soup.find(selector)
            if element:
                text = element.get_text(separator="\n", strip=True)
                if text:
                    return text[:max_chars]

        # Fallback: entire document text
        text = soup.get_text(separator="\n", strip=True)
        return text[:max_chars]
