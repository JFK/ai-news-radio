"""Tests for ScriptwriterStep pipeline step."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiUsage, NewsItem, StepName
from app.pipeline.engine import PipelineEngine
from app.pipeline.scriptwriter import ScriptwriterStep
from app.services.ai_provider import AIResponse


@pytest.fixture
def scriptwriter() -> ScriptwriterStep:
    return ScriptwriterStep()


def _make_script_item_response(title: str = "テスト") -> AIResponse:
    """Create a mock AIResponse for per-item script generation."""
    return AIResponse(
        content=json.dumps({"script_text": f"ひとことで言うと、{title}についてのニュースです。背景として..."}),
        input_tokens=200,
        output_tokens=400,
        model="test-model",
        provider="test-provider",
    )


def _make_episode_composition_response(n_transitions: int = 1) -> AIResponse:
    """Create a mock AIResponse for episode composition."""
    return AIResponse(
        content=json.dumps(
            {
                "opening": "皆さん、こんにちは。今日のニュースラジオです。",
                "transitions": ["続いてはこちらのニュースです。" for _ in range(n_transitions)],
                "ending": "今日のニュースは以上です。また次回お会いしましょう。",
            }
        ),
        input_tokens=300,
        output_tokens=500,
        model="test-model",
        provider="test-provider",
    )


async def _create_episode_with_items(
    session: AsyncSession,
    n_items: int = 2,
) -> tuple[int, list[int]]:
    """Create an episode with N news items with analysis data."""
    engine = PipelineEngine()
    episode = await engine.create_episode("Test Episode", session)

    item_ids = []
    for i in range(n_items):
        item = NewsItem(
            episode_id=episode.id,
            title=f"テストニュース {i}",
            summary=f"テスト要約 {i}",
            source_url=f"https://example.com/news/{i}",
            source_name="TestSource",
            fact_check_status="verified",
            fact_check_score=4,
            analysis_data={
                "background": "テスト背景",
                "why_now": "テストの理由",
                "perspectives": [
                    {"standpoint": "行政側", "argument": "主張A", "basis": "根拠A"},
                    {"standpoint": "住民側", "argument": "主張B", "basis": "根拠B"},
                    {"standpoint": "専門家", "argument": "主張C", "basis": "根拠C"},
                ],
                "data_validation": "妥当",
                "impact": "影響あり",
                "uncertainties": "未確認事項あり",
            },
        )
        session.add(item)
        await session.flush()
        item_ids.append(item.id)

    await session.commit()
    return episode.id, item_ids


class TestScriptwriterStep:
    """Tests for the script generation pipeline step."""

    def test_step_name(self, scriptwriter: ScriptwriterStep):
        assert scriptwriter.step_name == StepName.SCRIPT

    @patch("app.pipeline.scriptwriter.get_step_provider")
    @patch("app.pipeline.scriptwriter.async_session")
    async def test_execute_stores_script_text(
        self,
        mock_session_factory,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """execute() should store script_text on each NewsItem."""
        episode_id, item_ids = await _create_episode_with_items(session, 2)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_script_item_response("ニュース0"),
            _make_script_item_response("ニュース1"),
            _make_episode_composition_response(1),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        result = await scriptwriter.execute(episode_id, {})

        assert result["items_scripted"] == 2

        for item_id in item_ids:
            db_result = await session.execute(select(NewsItem).where(NewsItem.id == item_id))
            item = db_result.scalar_one()
            assert item.script_text is not None
            assert "ひとことで言うと" in item.script_text

    @patch("app.pipeline.scriptwriter.get_step_provider")
    @patch("app.pipeline.scriptwriter.async_session")
    async def test_episode_script_generated(
        self,
        mock_session_factory,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """execute() should generate a full episode script."""
        episode_id, _ = await _create_episode_with_items(session, 2)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_script_item_response("ニュース0"),
            _make_script_item_response("ニュース1"),
            _make_episode_composition_response(1),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        result = await scriptwriter.execute(episode_id, {})

        assert "episode_script" in result
        assert "皆さん、こんにちは" in result["episode_script"]
        assert "また次回お会いしましょう" in result["episode_script"]

    @patch("app.pipeline.scriptwriter.get_step_provider")
    @patch("app.pipeline.scriptwriter.async_session")
    async def test_ai_call_count(
        self,
        mock_session_factory,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """N items should result in N+1 AI calls (N per-item + 1 composition)."""
        n_items = 3
        episode_id, _ = await _create_episode_with_items(session, n_items)

        mock_provider = AsyncMock()
        responses = [_make_script_item_response(f"ニュース{i}") for i in range(n_items)]
        responses.append(_make_episode_composition_response(n_items - 1))
        mock_provider.generate.side_effect = responses
        mock_get_provider.return_value = (mock_provider, "test-model")

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await scriptwriter.execute(episode_id, {})

        assert mock_provider.generate.call_count == n_items + 1

    @patch("app.pipeline.scriptwriter.get_step_provider")
    @patch("app.pipeline.scriptwriter.async_session")
    async def test_execute_records_api_usage(
        self,
        mock_session_factory,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """execute() should record ApiUsage for each AI call."""
        episode_id, _ = await _create_episode_with_items(session, 2)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_script_item_response("ニュース0"),
            _make_script_item_response("ニュース1"),
            _make_episode_composition_response(1),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        await scriptwriter.execute(episode_id, {})

        db_result = await session.execute(
            select(ApiUsage).where(
                ApiUsage.episode_id == episode_id,
                ApiUsage.step_name == "script",
            )
        )
        usages = db_result.scalars().all()
        assert len(usages) == 3  # 2 items + 1 composition

    @patch("app.pipeline.scriptwriter.get_step_provider")
    @patch("app.pipeline.scriptwriter.async_session")
    async def test_output_data_structure(
        self,
        mock_session_factory,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """output_data should contain expected keys."""
        episode_id, _ = await _create_episode_with_items(session, 1)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_script_item_response("ニュース0"),
            _make_episode_composition_response(0),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        result = await scriptwriter.execute(episode_id, {})

        assert "items_scripted" in result
        assert "item_scripts" in result
        assert "episode_script" in result
        assert "total_input_tokens" in result
        assert "total_output_tokens" in result
