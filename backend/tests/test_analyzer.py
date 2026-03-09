"""Tests for AnalyzerStep pipeline step."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiUsage, NewsItem, StepName
from app.pipeline.analyzer import AnalyzerStep
from app.services.ai_provider import AIResponse
from tests.helpers import create_episode_with_items


@pytest.fixture
def analyzer() -> AnalyzerStep:
    return AnalyzerStep()


def _make_analysis_response(severity: str = "medium") -> AIResponse:
    """Create a mock AIResponse with analysis JSON."""
    return AIResponse(
        content=json.dumps(
            {
                "background": "テスト背景",
                "why_now": "テストの理由",
                "perspectives": [
                    {"standpoint": "行政側", "argument": "主張A", "basis": "根拠A"},
                    {"standpoint": "住民側", "argument": "主張B", "basis": "根拠B"},
                    {"standpoint": "専門家", "argument": "主張C", "basis": "根拠C"},
                ],
                "data_validation": "数値は妥当",
                "impact": "生活への影響あり",
                "uncertainties": "一部未確認",
                "severity": severity,
                "topics": ["テスト", "ニュース"],
            }
        ),
        input_tokens=150,
        output_tokens=300,
        model="test-model",
        provider="test-provider",
    )


class TestAnalyzerStep:
    """Tests for the analysis pipeline step."""

    def test_step_name(self, analyzer: AnalyzerStep):
        assert analyzer.step_name == StepName.ANALYSIS

    @patch("app.pipeline.analyzer.get_step_provider")
    async def test_execute_stores_analysis_data(
        self,
        mock_get_provider,
        analyzer: AnalyzerStep,
        session: AsyncSession,
    ):
        """execute() should store analysis_data on each NewsItem."""
        episode_id, item_ids = await create_episode_with_items(session, 2)

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = _make_analysis_response()
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await analyzer.execute(episode_id, {}, session)

        assert result["items_analyzed"] == 2
        assert len(result["results"]) == 2

        for item_id in item_ids:
            db_result = await session.execute(select(NewsItem).where(NewsItem.id == item_id))
            item = db_result.scalar_one()
            assert item.analysis_data is not None
            assert item.analysis_data["background"] == "テスト背景"
            assert len(item.analysis_data["perspectives"]) == 3

    @patch("app.pipeline.analyzer.get_step_provider")
    async def test_factcheck_results_in_prompt(
        self,
        mock_get_provider,
        analyzer: AnalyzerStep,
        session: AsyncSession,
    ):
        """Fact-check results should be included in the AI prompt."""
        episode_id, _ = await create_episode_with_items(session, 1, with_factcheck=True)

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = _make_analysis_response()
        mock_get_provider.return_value = (mock_provider, "test-model")

        await analyzer.execute(episode_id, {}, session)

        # Check that the prompt sent to the AI contains fact-check info
        call_args = mock_provider.generate.call_args
        prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
        assert "ファクトチェック結果" in prompt
        assert "verified" in prompt

    @patch("app.pipeline.analyzer.get_step_provider")
    async def test_severity_summary(
        self,
        mock_get_provider,
        analyzer: AnalyzerStep,
        session: AsyncSession,
    ):
        """output_data should include severity_summary counts."""
        episode_id, _ = await create_episode_with_items(session, 3)

        mock_provider = AsyncMock()
        responses = [
            _make_analysis_response("high"),
            _make_analysis_response("medium"),
            _make_analysis_response("low"),
        ]
        mock_provider.generate.side_effect = responses
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await analyzer.execute(episode_id, {}, session)

        assert result["severity_summary"] == {"high": 1, "medium": 1, "low": 1}

    @patch("app.pipeline.analyzer.get_step_provider")
    async def test_execute_records_api_usage(
        self,
        mock_get_provider,
        analyzer: AnalyzerStep,
        session: AsyncSession,
    ):
        """execute() should record ApiUsage for each AI call."""
        episode_id, _ = await create_episode_with_items(session, 2)

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = _make_analysis_response()
        mock_get_provider.return_value = (mock_provider, "test-model")

        await analyzer.execute(episode_id, {}, session)

        db_result = await session.execute(
            select(ApiUsage).where(
                ApiUsage.episode_id == episode_id,
                ApiUsage.step_name == "analysis",
            )
        )
        usages = db_result.scalars().all()
        assert len(usages) == 2

    @patch("app.pipeline.analyzer.get_step_provider")
    async def test_output_data_structure(
        self,
        mock_get_provider,
        analyzer: AnalyzerStep,
        session: AsyncSession,
    ):
        """output_data should contain expected keys."""
        episode_id, _ = await create_episode_with_items(session, 1)

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = _make_analysis_response()
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await analyzer.execute(episode_id, {}, session)

        assert "items_analyzed" in result
        assert "results" in result
        assert "severity_summary" in result
        assert "total_input_tokens" in result
        assert "total_output_tokens" in result
