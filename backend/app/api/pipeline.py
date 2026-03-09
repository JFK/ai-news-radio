"""Pipeline step management API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import PipelineStep, StepName
from app.pipeline import engine

router = APIRouter(tags=["pipeline"])


# --- Schemas ---


class StepResponse(BaseModel):
    """Response for a single pipeline step."""

    id: int
    episode_id: int
    step_name: str
    status: str
    input_data: dict | None = None
    output_data: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunStepRequest(BaseModel):
    """Optional request body for running a step."""

    queries: list[str] | None = None  # Override collection queries


class RejectRequest(BaseModel):
    """Request body for rejecting a step."""

    reason: str


# --- Endpoints ---


@router.get("/episodes/{episode_id}/steps", response_model=list[StepResponse])
async def list_steps(
    episode_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[PipelineStep]:
    """List all pipeline steps for an episode."""
    result = await session.execute(
        select(PipelineStep).where(PipelineStep.episode_id == episode_id).order_by(PipelineStep.id)
    )
    return list(result.scalars().all())


@router.post("/episodes/{episode_id}/steps/{step_name}/run", response_model=StepResponse)
async def run_step(
    episode_id: int,
    step_name: str,
    body: RunStepRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> PipelineStep:
    """Execute a pipeline step.

    For the collection step, optional `queries` can override the default search queries.
    """
    try:
        step_enum = StepName(step_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid step name: {step_name}") from e

    try:
        kwargs = {}
        if body and body.queries and step_enum == StepName.COLLECTION:
            kwargs["queries"] = body.queries
        await engine.run_step(episode_id, step_enum, session, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Return the updated step
    result = await session.execute(
        select(PipelineStep).where(
            PipelineStep.episode_id == episode_id,
            PipelineStep.step_name == step_enum,
        )
    )
    return result.scalar_one()


@router.post("/steps/{step_id}/approve", response_model=StepResponse)
async def approve_step(
    step_id: int,
    session: AsyncSession = Depends(get_session),
) -> PipelineStep:
    """Approve a pipeline step."""
    try:
        return await engine.approve_step(step_id, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/steps/{step_id}/reject", response_model=StepResponse)
async def reject_step(
    step_id: int,
    body: RejectRequest,
    session: AsyncSession = Depends(get_session),
) -> PipelineStep:
    """Reject a pipeline step with a reason."""
    try:
        return await engine.reject_step(step_id, body.reason, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
