"""Tests for the from-articles episode creation API."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Episode, NewsItem, PipelineStep, StepName, StepStatus


SAMPLE_ARTICLES = [
    {
        "title": "テスト記事1",
        "summary": "テスト要約1",
        "source_url": "https://example.com/1",
        "source_name": "TestSource",
    },
    {
        "title": "テスト記事2",
        "summary": "テスト要約2",
        "source_url": "https://example.com/2",
        "source_name": "TestSource",
    },
]


class TestFromArticlesAPI:
    async def test_create_episode_from_articles(self, client: AsyncClient):
        response = await client.post(
            "/api/episodes/from-articles",
            json={"title": "テストエピソード", "articles": SAMPLE_ARTICLES},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "テストエピソード"
        assert data["status"] == "in_progress"

    async def test_collection_step_auto_approved(self, client: AsyncClient, session: AsyncSession):
        response = await client.post(
            "/api/episodes/from-articles",
            json={"title": "テスト", "articles": SAMPLE_ARTICLES},
        )
        episode_id = response.json()["id"]

        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode_id,
                PipelineStep.step_name == StepName.COLLECTION,
            )
        )
        step = result.scalar_one()
        assert step.status == StepStatus.APPROVED
        assert step.output_data["source"] == "api"
        assert step.output_data["articles_count"] == 2

    async def test_news_items_created(self, client: AsyncClient, session: AsyncSession):
        response = await client.post(
            "/api/episodes/from-articles",
            json={"title": "テスト", "articles": SAMPLE_ARTICLES},
        )
        episode_id = response.json()["id"]

        result = await session.execute(
            select(NewsItem).where(NewsItem.episode_id == episode_id).order_by(NewsItem.id)
        )
        items = list(result.scalars().all())
        assert len(items) == 2
        assert items[0].title == "テスト記事1"
        assert items[1].source_url == "https://example.com/2"

    async def test_factcheck_step_is_pending(self, client: AsyncClient, session: AsyncSession):
        response = await client.post(
            "/api/episodes/from-articles",
            json={"title": "テスト", "articles": SAMPLE_ARTICLES},
        )
        episode_id = response.json()["id"]

        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode_id,
                PipelineStep.step_name == StepName.FACTCHECK,
            )
        )
        step = result.scalar_one()
        assert step.status == StepStatus.PENDING

    async def test_empty_articles_returns_400(self, client: AsyncClient):
        response = await client.post(
            "/api/episodes/from-articles",
            json={"title": "テスト", "articles": []},
        )
        assert response.status_code == 400

    async def test_article_without_summary(self, client: AsyncClient, session: AsyncSession):
        response = await client.post(
            "/api/episodes/from-articles",
            json={
                "title": "テスト",
                "articles": [
                    {
                        "title": "タイトルのみ",
                        "source_url": "https://example.com/3",
                        "source_name": "TestSource",
                    }
                ],
            },
        )
        assert response.status_code == 201
        episode_id = response.json()["id"]

        result = await session.execute(
            select(NewsItem).where(NewsItem.episode_id == episode_id)
        )
        item = result.scalar_one()
        assert item.summary is None
