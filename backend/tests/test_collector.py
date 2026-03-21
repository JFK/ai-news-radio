"""Tests for CollectorStep pipeline step."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiUsage, NewsItem, StepName
from app.pipeline.collector import CollectorStep
from app.pipeline.engine import PipelineEngine
from app.services.brave_search import BraveSearchResult


@pytest.fixture
def collector() -> CollectorStep:
    return CollectorStep()


def _set_default_mock_settings(mock_settings: MagicMock) -> None:
    """Set default values for new settings attributes added by the deep-research feature."""
    mock_settings.collection_image_analysis_enabled = False
    mock_settings.collection_document_visual_analysis = False
    mock_settings.collection_academic_search_enabled = False
    mock_settings.collection_academic_max_papers = 5
    mock_settings.collection_translation_enabled = False
    mock_settings.collection_translation_provider = ""
    mock_settings.collection_translation_model = ""
    mock_settings.collection_deep_investigation_enabled = False
    mock_settings.collection_deep_investigation_max_rounds = 3
    mock_settings.collection_deep_investigation_max_cost_usd = 1.0
    mock_settings.collection_deep_investigation_provider = ""
    mock_settings.collection_deep_investigation_model = ""


def _make_brave_results(n: int = 3) -> list[BraveSearchResult]:
    """Create N sample BraveSearchResult instances."""
    return [
        BraveSearchResult(
            title=f"ニュース {i}",
            url=f"https://example.com/news/{i}",
            description=f"要約 {i}",
        )
        for i in range(n)
    ]


class TestCollectorStep:
    """Tests for the collection pipeline step."""

    def test_step_name(self, collector: CollectorStep):
        assert collector.step_name == StepName.COLLECTION

    @patch("app.pipeline.collector.settings")
    async def test_execute_creates_news_items_brave(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """execute() should create NewsItem records from Brave Search results."""
        mock_settings.collection_method = "brave"
        mock_settings.collection_queries = "熊本 ニュース"
        mock_settings.brave_search_api_key = "test-key"
        mock_settings.collection_crawl_enabled = False
        mock_settings.collection_youtube_enabled = False
        mock_settings.collection_document_enabled = False
        mock_settings.collection_ai_research_enabled = False
        _set_default_mock_settings(mock_settings)

        results = _make_brave_results(3)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with patch("app.services.brave_search.BraveSearchService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.web_search = AsyncMock(return_value=results)
            mock_service.query_count = 1
            mock_service_cls.return_value = mock_service

            result = await collector.execute(episode.id, {}, session)

        assert result["collection_method"] == "brave"
        assert result["articles_found"] == 3
        assert result["articles_saved"] == 3

        db_result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode.id))
        items = db_result.scalars().all()
        assert len(items) == 3

    @patch("app.pipeline.collector.settings")
    async def test_execute_idempotent(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """Running execute twice should not duplicate articles."""
        mock_settings.collection_method = "brave"
        mock_settings.collection_queries = "熊本 ニュース"
        mock_settings.brave_search_api_key = "test-key"
        mock_settings.collection_crawl_enabled = False
        mock_settings.collection_youtube_enabled = False
        mock_settings.collection_document_enabled = False
        mock_settings.collection_ai_research_enabled = False
        _set_default_mock_settings(mock_settings)

        results = _make_brave_results(2)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with patch("app.services.brave_search.BraveSearchService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.web_search = AsyncMock(return_value=results)
            mock_service.query_count = 1
            mock_service_cls.return_value = mock_service

            result1 = await collector.execute(episode.id, {}, session)
            result2 = await collector.execute(episode.id, {}, session)

        assert result1["articles_saved"] == 2
        assert result2["articles_saved"] == 0

    @patch("app.pipeline.collector.settings")
    async def test_execute_with_no_articles(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """execute() with no results returns zero counts."""
        mock_settings.collection_method = "brave"
        mock_settings.collection_queries = "熊本 ニュース"
        mock_settings.brave_search_api_key = "test-key"
        mock_settings.collection_crawl_enabled = False
        mock_settings.collection_youtube_enabled = False
        mock_settings.collection_document_enabled = False
        mock_settings.collection_ai_research_enabled = False
        _set_default_mock_settings(mock_settings)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with patch("app.services.brave_search.BraveSearchService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.web_search = AsyncMock(return_value=[])
            mock_service.query_count = 1
            mock_service_cls.return_value = mock_service

            result = await collector.execute(episode.id, {}, session)

        assert result["articles_found"] == 0
        assert result["articles_saved"] == 0
        assert result["articles"] == []

    @patch("app.pipeline.collector.settings")
    async def test_execute_unknown_method_raises(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """execute() with unknown method should raise ValueError."""
        mock_settings.collection_method = "unknown"

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with pytest.raises(ValueError, match="Unknown collection method"):
            await collector.execute(episode.id, {}, session)


class TestEnrichment:
    """Tests for article enrichment (crawl, YouTube, documents)."""

    @patch("app.pipeline.collector.settings")
    async def test_crawl_enabled_enriches_articles(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """When crawl is enabled, articles should get body text."""
        mock_settings.collection_method = "brave"
        mock_settings.collection_queries = "テスト"
        mock_settings.brave_search_api_key = "test-key"
        mock_settings.collection_crawl_enabled = True
        mock_settings.collection_crawl_timeout = 5.0
        mock_settings.collection_crawl_max_body_chars = 50000
        mock_settings.collection_youtube_enabled = False
        mock_settings.collection_document_enabled = False
        mock_settings.collection_ai_research_enabled = False
        _set_default_mock_settings(mock_settings)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        from app.services.web_crawler import CrawlResult

        mock_crawl_result = CrawlResult(body="Full article text here", content_type="text/html", success=True)

        with (
            patch("app.services.brave_search.BraveSearchService") as mock_search_cls,
            patch("app.services.web_crawler.WebCrawlerService") as mock_crawler_cls,
        ):
            mock_search = MagicMock()
            mock_search.query_count = 1
            mock_search.web_search = AsyncMock(return_value=_make_brave_results(2))
            mock_search_cls.return_value = mock_search

            mock_crawler = MagicMock()
            mock_crawler.crawl = AsyncMock(return_value=mock_crawl_result)
            mock_crawler_cls.return_value = mock_crawler

            result = await collector.execute(episode.id, {}, session)

        assert result["enrichment"]["crawled"] == 2
        assert result["enrichment"]["errors"] == 0

        db_result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode.id))
        items = db_result.scalars().all()
        for item in items:
            assert item.body == "Full article text here"

    @patch("app.pipeline.collector.settings")
    async def test_crawl_disabled_skips_enrichment(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """When crawl is disabled, articles should not get body text."""
        mock_settings.collection_method = "brave"
        mock_settings.collection_queries = "テスト"
        mock_settings.brave_search_api_key = "test-key"
        mock_settings.collection_crawl_enabled = False
        mock_settings.collection_youtube_enabled = False
        mock_settings.collection_document_enabled = False
        mock_settings.collection_ai_research_enabled = False
        _set_default_mock_settings(mock_settings)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with patch("app.services.brave_search.BraveSearchService") as mock_search_cls:
            mock_search = MagicMock()
            mock_search.query_count = 1
            mock_search.web_search = AsyncMock(return_value=_make_brave_results(1))
            mock_search_cls.return_value = mock_search

            result = await collector.execute(episode.id, {}, session)

        assert result["enrichment"]["crawled"] == 0

        db_result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode.id))
        items = db_result.scalars().all()
        for item in items:
            assert item.body is None

    @patch("app.pipeline.collector.settings")
    async def test_crawl_failure_graceful(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """Crawl failure should not break the pipeline."""
        mock_settings.collection_method = "brave"
        mock_settings.collection_queries = "テスト"
        mock_settings.brave_search_api_key = "test-key"
        mock_settings.collection_crawl_enabled = True
        mock_settings.collection_crawl_timeout = 5.0
        mock_settings.collection_crawl_max_body_chars = 50000
        mock_settings.collection_youtube_enabled = False
        mock_settings.collection_document_enabled = False
        mock_settings.collection_ai_research_enabled = False
        _set_default_mock_settings(mock_settings)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        from app.services.web_crawler import CrawlResult

        mock_crawl_result = CrawlResult(body="", content_type="", success=False, error="Connection timeout")

        with (
            patch("app.services.brave_search.BraveSearchService") as mock_search_cls,
            patch("app.services.web_crawler.WebCrawlerService") as mock_crawler_cls,
        ):
            mock_search = MagicMock()
            mock_search.query_count = 1
            mock_search.web_search = AsyncMock(return_value=_make_brave_results(1))
            mock_search_cls.return_value = mock_search

            mock_crawler = MagicMock()
            mock_crawler.crawl = AsyncMock(return_value=mock_crawl_result)
            mock_crawler_cls.return_value = mock_crawler

            result = await collector.execute(episode.id, {}, session)

        assert result["enrichment"]["errors"] == 1
        assert result["articles_saved"] == 1


class TestAIResearch:
    """Tests for AI multi-stage research."""

    @patch("app.pipeline.collector.settings")
    async def test_ai_research_sets_factcheck_included(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """AI research should set factcheck_included=True in output."""
        mock_settings.collection_method = "brave"
        mock_settings.collection_queries = "テスト"
        mock_settings.brave_search_api_key = "test-key"
        mock_settings.collection_crawl_enabled = False
        mock_settings.collection_youtube_enabled = False
        mock_settings.collection_document_enabled = False
        mock_settings.collection_ai_research_enabled = True
        mock_settings.collection_ai_research_max_rounds = 1
        mock_settings.collection_ai_research_provider = ""
        mock_settings.collection_ai_research_model = ""
        _set_default_mock_settings(mock_settings)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        from app.services.ai_provider import AIResponse

        plan_response = AIResponse(
            content=json.dumps({
                "claims_to_verify": [{"article_index": 0, "claim": "Test", "reason": "Verify"}],
                "search_queries": ["追加クエリ1"],
            }),
            input_tokens=100, output_tokens=200, model="test", provider="test",
        )
        integrate_response = AIResponse(
            content=json.dumps({
                "results": [{
                    "article_index": 0,
                    "fact_check_status": "verified",
                    "fact_check_score": 4,
                    "fact_check_details": "確認済み",
                    "reference_urls": ["https://ref.example.com"],
                    "key_claims": [],
                }],
            }),
            input_tokens=200, output_tokens=300, model="test", provider="test",
        )

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(side_effect=[plan_response, integrate_response])

        additional_search_results = [
            BraveSearchResult(title="Ref", url="https://ref.example.com", description="Reference"),
        ]

        with (
            patch("app.services.brave_search.BraveSearchService") as mock_search_cls,
            patch("app.services.ai_provider.get_step_provider", return_value=(mock_provider, "test-model")),
        ):
            mock_search = MagicMock()
            mock_search.query_count = 1
            mock_search.web_search = AsyncMock(side_effect=[
                _make_brave_results(1),  # Initial collection
                additional_search_results,  # AI research additional search
            ])
            mock_search_cls.return_value = mock_search

            result = await collector.execute(episode.id, {}, session)

        assert result.get("factcheck_included") is True

        # Verify fact-check data written to NewsItem
        db_result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode.id))
        items = db_result.scalars().all()
        assert len(items) == 1
        assert items[0].fact_check_status == "verified"
        assert items[0].fact_check_score == 4

    @patch("app.pipeline.collector.settings")
    async def test_ai_research_disabled_by_default(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """AI research should not run when disabled."""
        mock_settings.collection_method = "brave"
        mock_settings.collection_queries = "テスト"
        mock_settings.brave_search_api_key = "test-key"
        mock_settings.collection_crawl_enabled = False
        mock_settings.collection_youtube_enabled = False
        mock_settings.collection_document_enabled = False
        mock_settings.collection_ai_research_enabled = False
        _set_default_mock_settings(mock_settings)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with patch("app.services.brave_search.BraveSearchService") as mock_search_cls:
            mock_search = MagicMock()
            mock_search.query_count = 1
            mock_search.web_search = AsyncMock(return_value=_make_brave_results(1))
            mock_search_cls.return_value = mock_search

            result = await collector.execute(episode.id, {}, session)

        assert result.get("factcheck_included") is None


class TestBraveSearchCostTracking:
    """Tests for Brave Search API cost tracking in collector."""

    @patch("app.pipeline.collector.settings")
    async def test_brave_search_records_api_usage(
        self, mock_settings, collector: CollectorStep, session: AsyncSession
    ):
        """Brave Search queries should be recorded as ApiUsage."""
        mock_settings.collection_method = "brave"
        mock_settings.collection_queries = "テスト"
        mock_settings.brave_search_api_key = "test-key"
        mock_settings.collection_crawl_enabled = False
        mock_settings.collection_youtube_enabled = False
        mock_settings.collection_document_enabled = False
        mock_settings.collection_ai_research_enabled = False
        _set_default_mock_settings(mock_settings)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with patch("app.services.brave_search.BraveSearchService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.web_search = AsyncMock(return_value=_make_brave_results(2))
            mock_service.query_count = 1
            mock_service_cls.return_value = mock_service

            await collector.execute(episode.id, {}, session)

        # Verify Brave Search usage recorded
        db_result = await session.execute(
            select(ApiUsage).where(
                ApiUsage.episode_id == episode.id,
                ApiUsage.provider == "brave",
            )
        )
        usages = db_result.scalars().all()
        assert len(usages) == 1
        assert usages[0].model == "brave-search"
        assert usages[0].input_tokens == 1
        assert usages[0].output_tokens == 0
        assert usages[0].cost_usd == pytest.approx(0.005)
