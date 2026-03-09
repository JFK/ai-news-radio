"""Base class for pipeline steps.

Each pipeline step inherits from BaseStep and implements execute().
The run() method handles the common workflow: status tracking, data flow, error handling.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiUsage, NewsItem, PipelineStep, StepName, StepStatus
from app.services.ai_provider import STEP_ORDER
from app.services.cost_estimator import estimate_cost


class BaseStep(ABC):
    """Abstract base class for pipeline steps."""

    @property
    @abstractmethod
    def step_name(self) -> StepName:
        """The name of this pipeline step."""
        ...

    @abstractmethod
    async def execute(self, episode_id: int, input_data: dict, **kwargs) -> dict:
        """Execute the step logic.

        Args:
            episode_id: The episode being processed.
            input_data: Output from the previous step (or empty dict for first step).
            **kwargs: Step-specific parameters (e.g., queries for collection).

        Returns:
            Output data to be stored and passed to the next step.
        """
        ...

    async def run(self, episode_id: int, session: AsyncSession, **kwargs) -> None:
        """Run this pipeline step with full lifecycle management.

        1. Set status to RUNNING
        2. Get input_data from previous step's output_data
        3. Call execute()
        4. Save output_data and set status to NEEDS_APPROVAL
        5. On error, reset status to PENDING
        """
        # Get the pipeline step record
        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode_id,
                PipelineStep.step_name == self.step_name,
            )
        )
        step = result.scalar_one()

        # Mark as running
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now(UTC)
        await session.commit()

        try:
            # Get input from previous step
            input_data = await self._get_input_data(episode_id, session)

            # Execute the step logic
            output_data = await self.execute(episode_id, input_data, **kwargs)

            # Save results
            step.input_data = input_data
            step.output_data = output_data
            step.status = StepStatus.NEEDS_APPROVAL
            step.completed_at = datetime.now(UTC)
            await session.commit()

        except Exception:
            # Reset to PENDING on error
            step.status = StepStatus.PENDING
            step.started_at = None
            await session.commit()
            raise

    async def _get_news_items(self, episode_id: int, session: AsyncSession) -> list[NewsItem]:
        """Load all NewsItems for the episode."""
        result = await session.execute(
            select(NewsItem).where(NewsItem.episode_id == episode_id).order_by(NewsItem.id)
        )
        return list(result.scalars().all())

    async def _get_input_data(self, episode_id: int, session: AsyncSession) -> dict:
        """Get the output_data from the previous step as input for this step."""
        prev_step_name = self.get_previous_step()
        if prev_step_name is None:
            return {}

        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode_id,
                PipelineStep.step_name == prev_step_name,
            )
        )
        prev_step = result.scalar_one()
        return prev_step.output_data or {}

    def get_previous_step(self) -> StepName | None:
        """Get the previous step in the pipeline order."""
        current_index = STEP_ORDER.index(self.step_name.value)
        if current_index == 0:
            return None
        prev_value = STEP_ORDER[current_index - 1]
        return StepName(prev_value)

    async def record_usage(
        self,
        session: AsyncSession,
        episode_id: int,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float | None = None,
    ) -> ApiUsage:
        """Record API usage for cost tracking.

        If cost_usd is not provided, it will be estimated from the model_pricing table.
        """
        if cost_usd is None:
            cost_usd = await estimate_cost(session, model, input_tokens, output_tokens)

        usage = ApiUsage(
            episode_id=episode_id,
            step_name=self.step_name.value,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
        session.add(usage)
        await session.commit()
        return usage
