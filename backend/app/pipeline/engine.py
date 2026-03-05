"""Pipeline execution engine.

Manages episode creation, step execution, and approval/rejection workflow.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Episode, EpisodeStatus, PipelineStep, StepName, StepStatus
from app.pipeline.base import BaseStep
from app.services.ai_provider import STEP_ORDER


class PipelineEngine:
    """Orchestrates pipeline execution and approval workflow."""

    def __init__(self) -> None:
        self._step_registry: dict[StepName, type[BaseStep]] = {}

    def register_step(self, step_class: type[BaseStep]) -> None:
        """Register a step implementation."""
        instance = step_class()
        self._step_registry[instance.step_name] = step_class

    async def create_episode(self, title: str, session: AsyncSession) -> Episode:
        """Create a new episode with all 7 pipeline steps in PENDING status."""
        episode = Episode(title=title, status=EpisodeStatus.DRAFT)
        session.add(episode)
        await session.flush()

        for step_value in STEP_ORDER:
            step = PipelineStep(
                episode_id=episode.id,
                step_name=StepName(step_value),
                status=StepStatus.PENDING,
            )
            session.add(step)

        await session.commit()
        await session.refresh(episode)
        return episode

    async def run_step(self, episode_id: int, step_name: StepName, session: AsyncSession) -> None:
        """Execute a specific pipeline step."""
        # Verify step is registered
        step_class = self._step_registry.get(step_name)
        if step_class is None:
            raise ValueError(f"No implementation registered for step: {step_name.value}")

        # Verify previous step is approved (except for first step)
        step_index = STEP_ORDER.index(step_name.value)
        if step_index > 0:
            prev_step_name = StepName(STEP_ORDER[step_index - 1])
            result = await session.execute(
                select(PipelineStep).where(
                    PipelineStep.episode_id == episode_id,
                    PipelineStep.step_name == prev_step_name,
                )
            )
            prev_step = result.scalar_one()
            if prev_step.status != StepStatus.APPROVED:
                raise ValueError(
                    f"Previous step '{prev_step_name.value}' must be approved before running '{step_name.value}'"
                )

        # Update episode status
        result = await session.execute(select(Episode).where(Episode.id == episode_id))
        episode = result.scalar_one()
        if episode.status == EpisodeStatus.DRAFT:
            episode.status = EpisodeStatus.IN_PROGRESS
            await session.commit()

        # Run the step
        step_instance = step_class()
        await step_instance.run(episode_id, session)

    async def approve_step(self, step_id: int, session: AsyncSession) -> PipelineStep:
        """Approve a pipeline step that is awaiting approval."""
        result = await session.execute(select(PipelineStep).where(PipelineStep.id == step_id))
        step = result.scalar_one()

        if step.status != StepStatus.NEEDS_APPROVAL:
            raise ValueError(f"Step is not awaiting approval (current status: {step.status.value})")

        step.status = StepStatus.APPROVED
        step.approved_at = datetime.now(UTC)
        await session.commit()
        return step

    async def reject_step(self, step_id: int, reason: str, session: AsyncSession) -> PipelineStep:
        """Reject a pipeline step with a reason."""
        result = await session.execute(select(PipelineStep).where(PipelineStep.id == step_id))
        step = result.scalar_one()

        if step.status != StepStatus.NEEDS_APPROVAL:
            raise ValueError(f"Step is not awaiting approval (current status: {step.status.value})")

        step.status = StepStatus.REJECTED
        step.rejected_at = datetime.now(UTC)
        step.rejection_reason = reason
        await session.commit()
        return step

    async def get_episode_with_steps(self, episode_id: int, session: AsyncSession) -> Episode:
        """Get an episode with all its pipeline steps eagerly loaded."""
        result = await session.execute(
            select(Episode).where(Episode.id == episode_id).options(selectinload(Episode.pipeline_steps))
        )
        return result.scalar_one()
