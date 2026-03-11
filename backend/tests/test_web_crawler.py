"""Tests for WebCrawlerService."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.web_crawler import WebCrawlerService


@pytest.fixture
def crawler() -> WebCrawlerService:
    return WebCrawlerService()


def _mock_response(status_code: int = 200, text: str = "", content: bytes = b"", headers: dict | None = None) -> httpx.Response:
    """Create a mock httpx.Response with a request set (needed for raise_for_status)."""
    if headers is None:
        headers = {}
    request = httpx.Request("GET", "https://example.com")
    if text:
        return httpx.Response(status_code, text=text, headers=headers, request=request)
    return httpx.Response(status_code, content=content, headers=headers, request=request)


class TestWebCrawlerService:
    """Tests for web crawling and HTML text extraction."""

    async def test_crawl_extracts_article_text(self, crawler: WebCrawlerService):
        """Should extract text from <article> tag."""
        html = """
        <html><body>
            <nav>Navigation</nav>
            <article><p>Article body text here.</p></article>
            <footer>Footer</footer>
        </body></html>
        """
        response = _mock_response(200, text=html, headers={"content-type": "text/html"})
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            result = await crawler.crawl("https://example.com/news/1")

        assert result.success is True
        assert "Article body text here." in result.body
        assert "Navigation" not in result.body
        assert "Footer" not in result.body

    async def test_crawl_fallback_to_main(self, crawler: WebCrawlerService):
        """Should fall back to <main> if no <article>."""
        html = """
        <html><body>
            <nav>Nav</nav>
            <main><p>Main content here.</p></main>
        </body></html>
        """
        response = _mock_response(200, text=html, headers={"content-type": "text/html"})
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            result = await crawler.crawl("https://example.com/news/1")

        assert result.success is True
        assert "Main content here." in result.body

    async def test_crawl_fallback_to_body(self, crawler: WebCrawlerService):
        """Should fall back to <body> if no <article> or <main>."""
        html = "<html><body><p>Body text.</p></body></html>"
        response = _mock_response(200, text=html, headers={"content-type": "text/html"})
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            result = await crawler.crawl("https://example.com/news/1")

        assert result.success is True
        assert "Body text." in result.body

    async def test_crawl_truncates_long_text(self, crawler: WebCrawlerService):
        """Should truncate text to max_chars."""
        html = f"<html><body><article>{'A' * 1000}</article></body></html>"
        response = _mock_response(200, text=html, headers={"content-type": "text/html"})
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            result = await crawler.crawl("https://example.com/news/1", max_chars=100)

        assert result.success is True
        assert len(result.body) == 100

    async def test_crawl_non_html_returns_failure(self, crawler: WebCrawlerService):
        """Should return success=False for non-HTML content."""
        response = _mock_response(200, content=b"PDF data", headers={"content-type": "application/pdf"})
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            result = await crawler.crawl("https://example.com/file.pdf")

        assert result.success is False
        assert "Not HTML" in (result.error or "")

    async def test_crawl_http_error(self, crawler: WebCrawlerService):
        """Should handle HTTP errors gracefully."""
        response = _mock_response(404)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            result = await crawler.crawl("https://example.com/missing")

        assert result.success is False
        assert "404" in (result.error or "")

    async def test_crawl_network_error(self, crawler: WebCrawlerService):
        """Should handle network errors gracefully."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("timeout")):
            result = await crawler.crawl("https://example.com/timeout")

        assert result.success is False
        assert result.error is not None
