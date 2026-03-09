"""Tests for CollectorStep pipeline step."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewsItem, StepName
from app.pipeline.collector import CollectorStep
from app.pipeline.engine import PipelineEngine
from app.services.brave_search import BraveSearchResult


@pytest.fixture
def collector() -> CollectorStep:
    return CollectorStep()


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

        results = _make_brave_results(3)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with patch("app.services.brave_search.BraveSearchService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.web_search = AsyncMock(return_value=results)
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

        results = _make_brave_results(2)

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with patch("app.services.brave_search.BraveSearchService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.web_search = AsyncMock(return_value=results)
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

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        with patch("app.services.brave_search.BraveSearchService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.web_search = AsyncMock(return_value=[])
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
