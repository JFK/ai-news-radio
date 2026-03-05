"""Episode CRUD API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Episode
from app.pipeline.engine import PipelineEngine

router = APIRouter(tags=["episodes"])

engine = PipelineEngine()


# --- Schemas ---


class EpisodeCreate(BaseModel):
    """Request body for creating an episode."""

    title: str


class StepResponse(BaseModel):
    """Pipeline step in episode response."""

    id: int
    step_name: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None

    model_config = {"from_attributes": True}


class EpisodeResponse(BaseModel):
    """Response for a single episode."""

    id: int
    title: str
    status: str
    created_at: datetime
    published_at: datetime | None = None
    pipeline_steps: list[StepResponse] = []

    model_config = {"from_attributes": True}


class EpisodeListResponse(BaseModel):
    """Response for episode listing."""

    episodes: list[EpisodeResponse]
    total: int


# --- Endpoints ---


@router.post("/episodes", response_model=EpisodeResponse, status_code=201)
async def create_episode(
    body: EpisodeCreate,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    """Create a new episode with all 7 pipeline steps."""
    episode = await engine.create_episode(body.title, session)
    return await engine.get_episode_with_steps(episode.id, session)


@router.get("/episodes", response_model=EpisodeListResponse)
async def list_episodes(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List all episodes with their pipeline steps."""
    result = await session.execute(
        select(Episode).options(selectinload(Episode.pipeline_steps)).order_by(Episode.created_at.desc())
    )
    episodes = result.scalars().all()
    return {"episodes": episodes, "total": len(episodes)}


@router.get("/episodes/{episode_id}", response_model=EpisodeResponse)
async def get_episode(
    episode_id: int,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    """Get a single episode with its pipeline steps."""
    try:
        return await engine.get_episode_with_steps(episode_id, session)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Episode not found") from e
