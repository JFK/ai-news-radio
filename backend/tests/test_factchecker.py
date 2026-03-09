"""Tests for FactcheckerStep pipeline step."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiUsage, NewsItem, StepName
from app.pipeline.factchecker import FactcheckerStep
from app.services.ai_provider import AIResponse
from tests.helpers import create_episode_with_items


@pytest.fixture
def factchecker() -> FactcheckerStep:
    return FactcheckerStep()


def _make_ai_response(item_title: str = "Test") -> AIResponse:
    """Create a mock AIResponse with fact-check JSON."""
    return AIResponse(
        content=json.dumps(
            {
                "fact_check_status": "verified",
                "fact_check_score": 4,
                "fact_check_details": f"{item_title}の事実確認完了",
                "reference_urls": ["https://example.com/ref1"],
                "key_claims": [
                    {
                        "claim": "主要な主張",
                        "assessment": "confirmed",
                        "evidence": "確認済み",
                    }
                ],
            }
        ),
        input_tokens=100,
        output_tokens=200,
        model="test-model",
        provider="test-provider",
    )


class TestFactcheckerStep:
    """Tests for the fact-checking pipeline step."""

    def test_step_name(self, factchecker: FactcheckerStep):
        assert factchecker.step_name == StepName.FACTCHECK

    @patch("app.pipeline.factchecker.get_step_provider")
    async def test_execute_updates_all_items(
        self,
        mock_get_provider,
        factchecker: FactcheckerStep,
        session: AsyncSession,
    ):
        """execute() should fact-check and update all NewsItems."""
        episode_id, item_ids = await create_episode_with_items(session, 2)

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = _make_ai_response()
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await factchecker.execute(episode_id, {}, session)

        assert result["items_checked"] == 2
        assert len(result["results"]) == 2
        assert result["average_score"] == 4.0
        assert result["total_input_tokens"] == 200
        assert result["total_output_tokens"] == 400

        # Verify DB updates
        for item_id in item_ids:
            db_result = await session.execute(select(NewsItem).where(NewsItem.id == item_id))
            item = db_result.scalar_one()
            assert item.fact_check_status == "verified"
            assert item.fact_check_score == 4
            assert item.fact_check_details is not None
            assert item.reference_urls == ["https://example.com/ref1"]

    @patch("app.pipeline.factchecker.get_step_provider")
    async def test_execute_idempotent(
        self,
        mock_get_provider,
        factchecker: FactcheckerStep,
        session: AsyncSession,
    ):
        """Running execute twice should overwrite previous results."""
        episode_id, item_ids = await create_episode_with_items(session, 1)

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = _make_ai_response()
        mock_get_provider.return_value = (mock_provider, "test-model")

        # Run twice
        await factchecker.execute(episode_id, {}, session)

        # Change the response for second run
        mock_provider.generate.return_value = AIResponse(
            content=json.dumps(
                {
                    "fact_check_status": "disputed",
                    "fact_check_score": 2,
                    "fact_check_details": "再検証結果",
                    "reference_urls": [],
                    "key_claims": [],
                }
            ),
            input_tokens=50,
            output_tokens=100,
            model="test-model",
            provider="test-provider",
        )

        result = await factchecker.execute(episode_id, {}, session)

        # Should have overwritten
        db_result = await session.execute(select(NewsItem).where(NewsItem.id == item_ids[0]))
        item = db_result.scalar_one()
        assert item.fact_check_status == "disputed"
        assert item.fact_check_score == 2
        assert result["items_checked"] == 1

    @patch("app.pipeline.factchecker.get_step_provider")
    async def test_execute_records_api_usage(
        self,
        mock_get_provider,
        factchecker: FactcheckerStep,
        session: AsyncSession,
    ):
        """execute() should record ApiUsage for each AI call."""
        episode_id, _ = await create_episode_with_items(session, 2)

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = _make_ai_response()
        mock_get_provider.return_value = (mock_provider, "test-model")

        await factchecker.execute(episode_id, {}, session)

        db_result = await session.execute(
            select(ApiUsage).where(
                ApiUsage.episode_id == episode_id,
                ApiUsage.step_name == "factcheck",
            )
        )
        usages = db_result.scalars().all()
        assert len(usages) == 2
        assert usages[0].input_tokens == 100
        assert usages[0].output_tokens == 200

    @patch("app.pipeline.factchecker.get_step_provider")
    async def test_execute_empty_episode(
        self,
        mock_get_provider,
        factchecker: FactcheckerStep,
        session: AsyncSession,
    ):
        """execute() with no news items returns empty results."""
        episode_id, _ = await create_episode_with_items(session, 0)

        mock_provider = AsyncMock()
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await factchecker.execute(episode_id, {}, session)

        assert result["items_checked"] == 0
        assert result["results"] == []
        assert result["average_score"] == 0
        mock_provider.generate.assert_not_called()

    @patch("app.pipeline.factchecker.get_step_provider")
    async def test_output_data_structure(
        self,
        mock_get_provider,
        factchecker: FactcheckerStep,
        session: AsyncSession,
    ):
        """output_data should contain expected keys."""
        episode_id, _ = await create_episode_with_items(session, 1)

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = _make_ai_response()
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await factchecker.execute(episode_id, {}, session)

        assert "items_checked" in result
        assert "results" in result
        assert "average_score" in result
        assert "total_input_tokens" in result
        assert "total_output_tokens" in result
