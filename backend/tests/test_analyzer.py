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


def _make_grouping_response(ungrouped_ids: list[int] | None = None, groups: list | None = None) -> AIResponse:
    """Create a mock AIResponse for the grouping step."""
    return AIResponse(
        content=json.dumps(
            {
                "groups": groups or [],
                "ungrouped_ids": ungrouped_ids or [],
            }
        ),
        input_tokens=50,
        output_tokens=50,
        model="test-model",
        provider="test-provider",
    )


def _make_group_analysis_response() -> AIResponse:
    """Create a mock AIResponse with integrated group analysis JSON."""
    return AIResponse(
        content=json.dumps(
            {
                "background": "統合背景",
                "why_now": "統合理由",
                "perspectives": [
                    {"standpoint": "行政側", "argument": "主張A", "basis": "根拠A"},
                    {"standpoint": "住民側", "argument": "主張B", "basis": "根拠B"},
                    {"standpoint": "専門家", "argument": "主張C", "basis": "根拠C"},
                ],
                "data_validation": "ソース間で数値一致",
                "impact": "統合影響",
                "uncertainties": "統合不確実性",
                "source_comparison": "NHKとTestSourceで一致",
                "severity": "high",
                "topics": ["統合テスト"],
            }
        ),
        input_tokens=200,
        output_tokens=400,
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
        # First call: grouping (2 items), then 2 analysis calls
        mock_provider.generate.side_effect = [
            _make_grouping_response(item_ids),
            _make_analysis_response(),
            _make_analysis_response(),
        ]
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
        episode_id, item_ids = await create_episode_with_items(session, 3)

        mock_provider = AsyncMock()
        responses = [
            _make_grouping_response(item_ids),  # grouping call
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
        episode_id, item_ids = await create_episode_with_items(session, 2)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_grouping_response(item_ids),
            _make_analysis_response(),
            _make_analysis_response(),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        await analyzer.execute(episode_id, {}, session)

        db_result = await session.execute(
            select(ApiUsage).where(
                ApiUsage.episode_id == episode_id,
                ApiUsage.step_name == "analysis",
            )
        )
        usages = db_result.scalars().all()
        # 1 grouping call + 2 analysis calls = 3 usages
        assert len(usages) == 3

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
        assert "groups" in result
        assert "severity_summary" in result
        assert "total_input_tokens" in result
        assert "total_output_tokens" in result

    @patch("app.pipeline.analyzer.get_step_provider")
    async def test_grouped_analysis(
        self,
        mock_get_provider,
        analyzer: AnalyzerStep,
        session: AsyncSession,
    ):
        """Grouped items should get integrated analysis; non-primary items get merged_into marker."""
        episode_id, item_ids = await create_episode_with_items(session, 3)

        mock_provider = AsyncMock()
        # Grouping: items 0 and 1 grouped, item 2 ungrouped
        grouping_resp = _make_grouping_response(
            ungrouped_ids=[item_ids[2]],
            groups=[{
                "group_id": 1,
                "reason": "同じ事件の報道",
                "primary_id": item_ids[0],
                "member_ids": [item_ids[0], item_ids[1]],
            }],
        )
        mock_provider.generate.side_effect = [
            grouping_resp,
            _make_group_analysis_response(),  # group analysis
            _make_analysis_response(),        # ungrouped item
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await analyzer.execute(episode_id, {}, session)

        # 1 group result + 1 ungrouped result = 2
        assert result["items_analyzed"] == 2
        assert len(result["groups"]) == 1
        assert result["groups"][0]["primary_id"] == item_ids[0]

        # Primary item has full analysis
        primary = await session.get(NewsItem, item_ids[0])
        assert primary.group_id == 1
        assert primary.is_group_primary is True
        assert primary.analysis_data["background"] == "統合背景"
        assert primary.analysis_data.get("source_comparison") is not None

        # Non-primary item has merged_into marker
        secondary = await session.get(NewsItem, item_ids[1])
        assert secondary.group_id == 1
        assert secondary.is_group_primary is False
        assert secondary.analysis_data == {"merged_into": item_ids[0]}

        # Ungrouped item has normal analysis
        ungrouped = await session.get(NewsItem, item_ids[2])
        assert ungrouped.group_id is None
        assert ungrouped.is_group_primary is None
        assert ungrouped.analysis_data["background"] == "テスト背景"

    @patch("app.pipeline.analyzer.get_step_provider")
    async def test_grouping_fallback_on_bad_json(
        self,
        mock_get_provider,
        analyzer: AnalyzerStep,
        session: AsyncSession,
    ):
        """If grouping AI returns bad JSON, all items should be analyzed individually."""
        episode_id, item_ids = await create_episode_with_items(session, 2)

        mock_provider = AsyncMock()
        bad_grouping = AIResponse(
            content="This is not valid JSON!!!",
            input_tokens=50, output_tokens=50,
            model="test-model", provider="test-provider",
        )
        mock_provider.generate.side_effect = [
            bad_grouping,
            _make_analysis_response(),
            _make_analysis_response(),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await analyzer.execute(episode_id, {}, session)

        # All items analyzed individually
        assert result["items_analyzed"] == 2
        assert len(result["groups"]) == 0

    @patch("app.pipeline.analyzer.get_step_provider")
    async def test_grouping_idempotent(
        self,
        mock_get_provider,
        analyzer: AnalyzerStep,
        session: AsyncSession,
    ):
        """Re-running analysis should reset group_id/is_group_primary."""
        episode_id, item_ids = await create_episode_with_items(session, 2)

        # Manually set grouping on items (simulate prior run)
        for item_id in item_ids:
            item = await session.get(NewsItem, item_id)
            item.group_id = 99
            item.is_group_primary = True
        await session.commit()

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_grouping_response(item_ids),
            _make_analysis_response(),
            _make_analysis_response(),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        await analyzer.execute(episode_id, {}, session)

        # Grouping should be reset (no groups detected in this run)
        for item_id in item_ids:
            item = await session.get(NewsItem, item_id)
            assert item.group_id is None
            assert item.is_group_primary is None
