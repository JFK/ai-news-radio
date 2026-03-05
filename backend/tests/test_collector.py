"""Tests for CollectorStep pipeline step."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewsItem, StepName
from app.pipeline.collector import CollectorStep
from app.pipeline.engine import PipelineEngine
from app.services.scrapers.base import ScrapedArticle


@pytest.fixture
def collector() -> CollectorStep:
    return CollectorStep()


def _make_articles(n: int = 3) -> list[ScrapedArticle]:
    """Create N sample ScrapedArticle instances."""
    return [
        ScrapedArticle(
            title=f"ニュース {i}",
            url=f"https://example.com/news/{i}",
            source_name="TestSource",
            summary=f"要約 {i}",
        )
        for i in range(n)
    ]


class TestCollectorStep:
    """Tests for the collection pipeline step."""

    def test_step_name(self, collector: CollectorStep):
        assert collector.step_name == StepName.COLLECTION

    @patch("app.pipeline.collector.ScraperService")
    @patch("app.pipeline.collector.async_session")
    async def test_execute_creates_news_items(
        self, mock_session_factory, mock_service_cls, collector: CollectorStep, session: AsyncSession
    ):
        """execute() should create NewsItem records for scraped articles."""
        # Setup mock scraper service
        articles = _make_articles(3)
        mock_service = AsyncMock()
        mock_service.collect_all.return_value = articles
        mock_service_cls.return_value = mock_service

        # Use the real test session via context manager mock
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        # Create episode first
        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        result = await collector.execute(episode.id, {})

        assert result["articles_found"] == 3
        assert result["articles_saved"] == 3
        assert len(result["articles"]) == 3

        # Verify NewsItems in DB
        db_result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode.id))
        items = db_result.scalars().all()
        assert len(items) == 3

    @patch("app.pipeline.collector.ScraperService")
    @patch("app.pipeline.collector.async_session")
    async def test_execute_idempotent(
        self, mock_session_factory, mock_service_cls, collector: CollectorStep, session: AsyncSession
    ):
        """Running execute twice should not duplicate articles."""
        articles = _make_articles(2)
        mock_service = AsyncMock()
        mock_service.collect_all.return_value = articles
        mock_service_cls.return_value = mock_service

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        # Run twice
        result1 = await collector.execute(episode.id, {})
        result2 = await collector.execute(episode.id, {})

        assert result1["articles_saved"] == 2
        assert result2["articles_saved"] == 0

        db_result = await session.execute(select(NewsItem).where(NewsItem.episode_id == episode.id))
        items = db_result.scalars().all()
        assert len(items) == 2

    @patch("app.pipeline.collector.ScraperService")
    @patch("app.pipeline.collector.async_session")
    async def test_execute_with_no_articles(
        self, mock_session_factory, mock_service_cls, collector: CollectorStep, session: AsyncSession
    ):
        """execute() with no articles returns zero counts."""
        mock_service = AsyncMock()
        mock_service.collect_all.return_value = []
        mock_service_cls.return_value = mock_service

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        engine = PipelineEngine()
        episode = await engine.create_episode("Test", session)

        result = await collector.execute(episode.id, {})

        assert result["articles_found"] == 0
        assert result["articles_saved"] == 0
        assert result["articles"] == []
