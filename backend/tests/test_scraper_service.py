"""Tests for ScraperService."""

from app.services.scraper import ScraperService, _deduplicate, _normalize_url
from app.services.scrapers.base import BaseScraper, ScrapedArticle, ScrapeResult


class TestNormalizeUrl:
    """Tests for URL normalization."""

    def test_lowercase_scheme_and_host(self):
        assert _normalize_url("HTTP://EXAMPLE.COM/path") == "http://example.com/path"

    def test_remove_trailing_slash(self):
        assert _normalize_url("https://example.com/path/") == "https://example.com/path"

    def test_preserve_root_path(self):
        assert _normalize_url("https://example.com/") == "https://example.com/"

    def test_remove_fragment(self):
        assert _normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_preserve_query_string(self):
        assert _normalize_url("https://example.com/page?id=1") == "https://example.com/page?id=1"


class TestDeduplicate:
    """Tests for article deduplication."""

    def test_removes_exact_duplicates(self):
        articles = [
            ScrapedArticle(title="A", url="https://example.com/1", source_name="src"),
            ScrapedArticle(title="A copy", url="https://example.com/1", source_name="src2"),
        ]
        result = _deduplicate(articles)
        assert len(result) == 1
        assert result[0].title == "A"

    def test_removes_trailing_slash_duplicates(self):
        articles = [
            ScrapedArticle(title="A", url="https://example.com/path/", source_name="src"),
            ScrapedArticle(title="B", url="https://example.com/path", source_name="src"),
        ]
        result = _deduplicate(articles)
        assert len(result) == 1

    def test_keeps_different_urls(self):
        articles = [
            ScrapedArticle(title="A", url="https://example.com/1", source_name="src"),
            ScrapedArticle(title="B", url="https://example.com/2", source_name="src"),
        ]
        result = _deduplicate(articles)
        assert len(result) == 2

    def test_case_insensitive_host_dedup(self):
        articles = [
            ScrapedArticle(title="A", url="https://Example.COM/page", source_name="src"),
            ScrapedArticle(title="B", url="https://example.com/page", source_name="src"),
        ]
        result = _deduplicate(articles)
        assert len(result) == 1

    def test_empty_list(self):
        assert _deduplicate([]) == []


class TestScraperServiceRegistry:
    """Tests for dynamic scraper registration."""

    def test_default_scrapers_registered(self):
        service = ScraperService()
        names = service.registered_names
        # NHK excluded (JWT auth required)
        assert "NHK熊本" not in names
        assert "熊本県公式" in names
        assert "RKK熊本放送" in names
        assert "KAB熊本朝日放送" in names

    def test_register_custom_scraper(self):
        import httpx

        class CustomScraper(BaseScraper):
            @property
            def source_name(self) -> str:
                return "Custom"

            @property
            def base_url(self) -> str:
                return "https://custom.example.com"

            async def scrape(self, client: httpx.AsyncClient) -> ScrapeResult:
                return ScrapeResult(source_name=self.source_name)

        service = ScraperService()
        service.register(CustomScraper)
        assert "Custom" in service.registered_names

    def test_unregister_scraper(self):
        service = ScraperService()
        service.unregister("熊本県公式")
        assert "熊本県公式" not in service.registered_names

    def test_unregister_nonexistent_is_noop(self):
        service = ScraperService()
        service.unregister("存在しないソース")  # should not raise


class TestScraperServiceCollectAll:
    """Tests for error isolation in collect_all."""

    async def test_empty_registry_returns_empty(self):
        service = ScraperService()
        # Remove all default scrapers
        for name in list(service.registered_names):
            service.unregister(name)
        result = await service.collect_all()
        assert result == []
