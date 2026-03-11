"""Tests for ScriptwriterStep pipeline step."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiUsage, NewsItem, StepName
from app.pipeline.scriptwriter import ScriptwriterStep
from app.services.ai_provider import AIResponse
from tests.helpers import create_episode_with_items


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


class TestScriptwriterStep:
    """Tests for the script generation pipeline step."""

    def test_step_name(self, scriptwriter: ScriptwriterStep):
        assert scriptwriter.step_name == StepName.SCRIPT

    @patch("app.pipeline.scriptwriter.get_step_provider")
    async def test_execute_stores_script_text(
        self,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """execute() should store script_text on each NewsItem."""
        episode_id, item_ids = await create_episode_with_items(session, 2, with_analysis=True)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_script_item_response("ニュース0"),
            _make_script_item_response("ニュース1"),
            _make_episode_composition_response(1),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await scriptwriter.execute(episode_id, {}, session)

        assert result["items_scripted"] == 2

        for item_id in item_ids:
            db_result = await session.execute(select(NewsItem).where(NewsItem.id == item_id))
            item = db_result.scalar_one()
            assert item.script_text is not None
            assert "ひとことで言うと" in item.script_text

    @patch("app.pipeline.scriptwriter.get_step_provider")
    async def test_episode_script_generated(
        self,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """execute() should generate a full episode script."""
        episode_id, _ = await create_episode_with_items(session, 2, with_analysis=True)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_script_item_response("ニュース0"),
            _make_script_item_response("ニュース1"),
            _make_episode_composition_response(1),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await scriptwriter.execute(episode_id, {}, session)

        assert "episode_script" in result
        assert "皆さん、こんにちは" in result["episode_script"]
        assert "また次回お会いしましょう" in result["episode_script"]

    @patch("app.pipeline.scriptwriter.get_step_provider")
    async def test_ai_call_count(
        self,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """N items should result in N+1 AI calls (N per-item + 1 composition)."""
        n_items = 3
        episode_id, _ = await create_episode_with_items(session, n_items, with_analysis=True)

        mock_provider = AsyncMock()
        responses = [_make_script_item_response(f"ニュース{i}") for i in range(n_items)]
        responses.append(_make_episode_composition_response(n_items - 1))
        mock_provider.generate.side_effect = responses
        mock_get_provider.return_value = (mock_provider, "test-model")

        await scriptwriter.execute(episode_id, {}, session)

        assert mock_provider.generate.call_count == n_items + 1

    @patch("app.pipeline.scriptwriter.get_step_provider")
    async def test_execute_records_api_usage(
        self,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """execute() should record ApiUsage for each AI call."""
        episode_id, _ = await create_episode_with_items(session, 2, with_analysis=True)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_script_item_response("ニュース0"),
            _make_script_item_response("ニュース1"),
            _make_episode_composition_response(1),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        await scriptwriter.execute(episode_id, {}, session)

        db_result = await session.execute(
            select(ApiUsage).where(
                ApiUsage.episode_id == episode_id,
                ApiUsage.step_name == "script",
            )
        )
        usages = db_result.scalars().all()
        assert len(usages) == 3  # 2 items + 1 composition

    @patch("app.pipeline.scriptwriter.get_step_provider")
    async def test_output_data_structure(
        self,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """output_data should contain expected keys."""
        episode_id, _ = await create_episode_with_items(session, 1, with_analysis=True)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = [
            _make_script_item_response("ニュース0"),
            _make_episode_composition_response(0),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await scriptwriter.execute(episode_id, {}, session)

        assert "items_scripted" in result
        assert "item_scripts" in result
        assert "episode_script" in result
        assert "total_input_tokens" in result
        assert "total_output_tokens" in result

    @patch("app.pipeline.scriptwriter.get_step_provider")
    async def test_group_filtering_skips_non_primary(
        self,
        mock_get_provider,
        scriptwriter: ScriptwriterStep,
        session: AsyncSession,
    ):
        """Non-primary group members should be skipped in script generation."""
        episode_id, item_ids = await create_episode_with_items(session, 3, with_analysis=True)

        # Set up grouping: items 0 (primary) and 1 (non-primary) grouped, item 2 ungrouped
        item0 = await session.get(NewsItem, item_ids[0])
        item0.group_id = 1
        item0.is_group_primary = True
        item1 = await session.get(NewsItem, item_ids[1])
        item1.group_id = 1
        item1.is_group_primary = False
        await session.commit()

        mock_provider = AsyncMock()
        # Only 2 per-item scripts (primary + ungrouped) + 1 composition = 3 calls
        mock_provider.generate.side_effect = [
            _make_script_item_response("ニュース0"),
            _make_script_item_response("ニュース2"),
            _make_episode_composition_response(1),
        ]
        mock_get_provider.return_value = (mock_provider, "test-model")

        result = await scriptwriter.execute(episode_id, {}, session)

        assert result["items_scripted"] == 2
        assert mock_provider.generate.call_count == 3

        # Non-primary item should have no script_text
        item1 = await session.get(NewsItem, item_ids[1])
        assert item1.script_text is None
