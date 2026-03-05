"""Tests for pipeline engine."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EpisodeStatus, PipelineStep, StepName, StepStatus
from app.pipeline.engine import PipelineEngine


@pytest.fixture
def engine() -> PipelineEngine:
    return PipelineEngine()


class TestCreateEpisode:
    """Tests for episode creation."""

    async def test_create_episode_sets_title_and_status(self, engine: PipelineEngine, session: AsyncSession):
        episode = await engine.create_episode("Test Episode", session)
        assert episode.title == "Test Episode"
        assert episode.status == EpisodeStatus.DRAFT

    async def test_create_episode_creates_seven_steps(self, engine: PipelineEngine, session: AsyncSession):
        episode = await engine.create_episode("Test Episode", session)
        result = await session.execute(select(PipelineStep).where(PipelineStep.episode_id == episode.id))
        steps = result.scalars().all()
        assert len(steps) == 7

    async def test_create_episode_steps_are_pending(self, engine: PipelineEngine, session: AsyncSession):
        episode = await engine.create_episode("Test Episode", session)
        result = await session.execute(select(PipelineStep).where(PipelineStep.episode_id == episode.id))
        steps = result.scalars().all()
        for step in steps:
            assert step.status == StepStatus.PENDING

    async def test_create_episode_has_all_step_names(self, engine: PipelineEngine, session: AsyncSession):
        episode = await engine.create_episode("Test Episode", session)
        result = await session.execute(select(PipelineStep).where(PipelineStep.episode_id == episode.id))
        steps = result.scalars().all()
        step_names = {step.step_name for step in steps}
        expected = {s for s in StepName}
        assert step_names == expected


class TestApproveStep:
    """Tests for step approval."""

    async def test_approve_step(self, engine: PipelineEngine, session: AsyncSession):
        episode = await engine.create_episode("Test", session)
        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode.id,
                PipelineStep.step_name == StepName.COLLECTION,
            )
        )
        step = result.scalar_one()

        # Set step to NEEDS_APPROVAL first
        step.status = StepStatus.NEEDS_APPROVAL
        await session.commit()

        approved = await engine.approve_step(step.id, session)
        assert approved.status == StepStatus.APPROVED
        assert approved.approved_at is not None

    async def test_approve_wrong_status_raises(self, engine: PipelineEngine, session: AsyncSession):
        episode = await engine.create_episode("Test", session)
        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode.id,
                PipelineStep.step_name == StepName.COLLECTION,
            )
        )
        step = result.scalar_one()

        with pytest.raises(ValueError, match="not awaiting approval"):
            await engine.approve_step(step.id, session)


class TestRejectStep:
    """Tests for step rejection."""

    async def test_reject_step(self, engine: PipelineEngine, session: AsyncSession):
        episode = await engine.create_episode("Test", session)
        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode.id,
                PipelineStep.step_name == StepName.COLLECTION,
            )
        )
        step = result.scalar_one()

        step.status = StepStatus.NEEDS_APPROVAL
        await session.commit()

        rejected = await engine.reject_step(step.id, "Quality issue", session)
        assert rejected.status == StepStatus.REJECTED
        assert rejected.rejected_at is not None
        assert rejected.rejection_reason == "Quality issue"

    async def test_reject_wrong_status_raises(self, engine: PipelineEngine, session: AsyncSession):
        episode = await engine.create_episode("Test", session)
        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode.id,
                PipelineStep.step_name == StepName.COLLECTION,
            )
        )
        step = result.scalar_one()

        with pytest.raises(ValueError, match="not awaiting approval"):
            await engine.reject_step(step.id, "Bad", session)
