"""Tests for DocumentParserService."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.document_parser import DocumentParserService, ParseResult


@pytest.fixture
def parser() -> DocumentParserService:
    return DocumentParserService()


def _mock_response(status_code: int = 200, content: bytes = b"", headers: dict | None = None) -> httpx.Response:
    """Create a mock httpx.Response with a request set."""
    request = httpx.Request("GET", "https://example.com")
    return httpx.Response(status_code, content=content, headers=headers or {}, request=request)


class TestDocumentURLDetection:
    """Tests for document URL detection."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://example.com/report.pdf", "pdf"),
            ("https://example.com/slides.pptx", "pptx"),
            ("https://example.com/report.PDF", "pdf"),
            ("https://example.com/file.pdf?download=true", "pdf"),
            ("https://example.com/news/article", None),
            ("https://example.com/file.doc", None),
        ],
    )
    def test_is_document_url(self, url: str, expected: str | None):
        assert DocumentParserService.is_document_url(url) == expected


class TestDocumentParsing:
    """Tests for document downloading and parsing (mocked)."""

    async def test_unsupported_url(self, parser: DocumentParserService):
        """Should return failure for non-document URL."""
        result = await parser.download_and_parse("https://example.com/article")
        assert result.success is False
        assert "Not a supported document URL" in (result.error or "")

    async def test_parse_pdf(self, parser: DocumentParserService):
        """Should parse PDF content (mocked)."""
        fake_pdf_bytes = b"fake-pdf-data"
        response = _mock_response(200, content=fake_pdf_bytes, headers={"content-type": "application/pdf"})

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response),
            patch.object(DocumentParserService, "_parse_pdf") as mock_parse,
        ):
            mock_parse.return_value = ParseResult(text="PDF content here", doc_type="pdf", pages=3, success=True)
            result = await parser.download_and_parse("https://example.com/report.pdf")

        assert result.success is True
        assert result.text == "PDF content here"
        assert result.doc_type == "pdf"
        assert result.pages == 3

    async def test_parse_pptx(self, parser: DocumentParserService):
        """Should parse PPTX content (mocked)."""
        fake_pptx_bytes = b"fake-pptx-data"
        response = _mock_response(200, content=fake_pptx_bytes, headers={"content-type": "application/vnd.openxmlformats"})

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response),
            patch.object(DocumentParserService, "_parse_pptx") as mock_parse,
        ):
            mock_parse.return_value = ParseResult(text="Slide content", doc_type="pptx", pages=5, success=True)
            result = await parser.download_and_parse("https://example.com/slides.pptx")

        assert result.success is True
        assert result.text == "Slide content"
        assert result.doc_type == "pptx"

    async def test_download_too_large(self, parser: DocumentParserService):
        """Should fail if file exceeds size limit."""
        large_content = b"x" * (21 * 1024 * 1024)  # 21MB
        response = _mock_response(200, content=large_content)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            result = await parser.download_and_parse("https://example.com/huge.pdf")

        assert result.success is False
        assert "too large" in (result.error or "")

    async def test_download_http_error(self, parser: DocumentParserService):
        """Should handle download failures gracefully."""
        response = _mock_response(500)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            result = await parser.download_and_parse("https://example.com/report.pdf")

        assert result.success is False
