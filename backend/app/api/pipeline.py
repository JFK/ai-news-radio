"""Pipeline step management API endpoints."""

import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings

from app.api.schemas import (
    ApproveRequest,
    EpisodeScriptEditRequest,
    RejectRequest,
    RunStepRequest,
    ScriptEditRequest,
    StepResponse,
)
from app.database import async_session as get_background_session
from app.database import get_session
from app.models import NewsItem, PipelineStep, StepName, StepStatus
from app.pipeline import engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline"])


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


@router.get("/episodes/{episode_id}/steps/{step_name}/logs")
async def get_step_logs(episode_id: int, step_name: str) -> dict:
    """Get real-time progress logs for a running step."""
    key = f"step_logs:{episode_id}:{step_name}"
    try:
        r = aioredis.from_url(app_settings.redis_url, socket_connect_timeout=2)
        raw_entries = await r.lrange(key, 0, -1)
        await r.aclose()
        logs = [json.loads(entry) for entry in raw_entries]
        return {"logs": logs}
    except Exception:
        return {"logs": []}


# Hold references to background tasks so they don't get GC'd
_background_tasks: set[asyncio.Task] = set()


async def _run_step_background(episode_id: int, step_name: StepName, **kwargs) -> None:
    """Execute a pipeline step in the background."""
    try:
        async with get_background_session() as session:
            await engine.run_step(episode_id, step_name, session, **kwargs)
        logger.info("Step %s for episode %d completed", step_name.value, episode_id)
    except Exception:
        logger.exception("Step %s for episode %d failed", step_name.value, episode_id)


@router.post("/episodes/{episode_id}/steps/{step_name}/run", response_model=StepResponse)
async def run_step(
    episode_id: int,
    step_name: str,
    body: RunStepRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> PipelineStep:
    """Execute a pipeline step in the background.

    Returns immediately with status 'running'. Poll the step to check completion.
    """
    try:
        step_enum = StepName(step_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid step name: {step_name}") from e

    # Validate before starting background task
    try:
        await engine.validate_step_runnable(episode_id, step_enum, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Mark as running immediately
    result = await session.execute(
        select(PipelineStep).where(
            PipelineStep.episode_id == episode_id,
            PipelineStep.step_name == step_enum,
        )
    )
    step = result.scalar_one()

    if step.status == StepStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Step is already running")

    # Launch background execution
    kwargs = {}
    if body and body.queries and step_enum == StepName.COLLECTION:
        kwargs["queries"] = body.queries
    if body and step_enum == StepName.VOICE:
        if body.tts_model:
            kwargs["tts_model"] = body.tts_model
        if body.tts_voice:
            kwargs["tts_voice"] = body.tts_voice
    task = asyncio.create_task(_run_step_background(episode_id, step_enum, **kwargs))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    # Return current step (will show RUNNING after base.run() sets it)
    await session.refresh(step)
    return step


@router.post("/steps/{step_id}/approve", response_model=StepResponse)
async def approve_step(
    step_id: int,
    body: ApproveRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> PipelineStep:
    """Approve a pipeline step, optionally excluding specific news items."""
    try:
        excluded_ids = body.excluded_item_ids if body else None
        return await engine.approve_step(step_id, session, excluded_item_ids=excluded_ids)
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


async def _get_script_step(episode_id: int, session: AsyncSession) -> PipelineStep:
    """Get the script step, validating it's editable."""
    result = await session.execute(
        select(PipelineStep).where(
            PipelineStep.episode_id == episode_id,
            PipelineStep.step_name == StepName.SCRIPT,
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        raise HTTPException(status_code=404, detail="Script step not found")

    if step.status not in (StepStatus.NEEDS_APPROVAL, StepStatus.APPROVED):
        raise HTTPException(
            status_code=400,
            detail=f"Script step must be needs_approval or approved to edit (current: {step.status.value})",
        )
    return step


async def _reset_voice_step(episode_id: int, session: AsyncSession) -> None:
    """Reset voice step to pending if it was already approved (requires re-generation)."""
    result = await session.execute(
        select(PipelineStep).where(
            PipelineStep.episode_id == episode_id,
            PipelineStep.step_name == StepName.VOICE,
        )
    )
    voice_step = result.scalar_one_or_none()
    if voice_step and voice_step.status == StepStatus.APPROVED:
        voice_step.status = StepStatus.PENDING
        voice_step.started_at = None
        voice_step.completed_at = None
        voice_step.approved_at = None


@router.patch("/episodes/{episode_id}/news-items/{news_item_id}/script")
async def edit_news_item_script(
    episode_id: int,
    news_item_id: int,
    body: ScriptEditRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Edit the script text for a single news item."""
    await _get_script_step(episode_id, session)

    result = await session.execute(
        select(NewsItem).where(NewsItem.id == news_item_id, NewsItem.episode_id == episode_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="News item not found")

    old_text = item.script_text
    item.script_text = body.script_text

    await _reset_voice_step(episode_id, session)
    await session.commit()

    return {"news_item_id": news_item_id, "old_length": len(old_text or ""), "new_length": len(body.script_text)}


@router.patch("/episodes/{episode_id}/steps/script/output")
async def edit_episode_script(
    episode_id: int,
    body: EpisodeScriptEditRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Edit the full episode script in the script step's output_data."""
    step = await _get_script_step(episode_id, session)

    if not step.output_data:
        raise HTTPException(status_code=400, detail="Script step has no output data")

    old_script = step.output_data.get("episode_script", "")
    step.output_data = {**step.output_data, "episode_script": body.episode_script}

    await _reset_voice_step(episode_id, session)
    await session.commit()

    return {"old_length": len(old_script), "new_length": len(body.episode_script)}
