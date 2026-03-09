"""Episode CRUD API endpoints."""

import os
import shutil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import (
    EpisodeCreate,
    EpisodeFromArticles,
    EpisodeListResponse,
    EpisodeResponse,
    NewsItemResponse,
)
from app.config import settings
from app.database import get_session
from app.models import Episode, NewsItem, StepStatus
from app.pipeline import engine

router = APIRouter(tags=["episodes"])


# --- Endpoints ---


@router.post("/episodes", response_model=EpisodeResponse, status_code=201)
async def create_episode(
    body: EpisodeCreate,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    """Create a new episode with all 7 pipeline steps."""
    episode = await engine.create_episode(body.title, session)
    return await engine.get_episode_with_steps(episode.id, session)


@router.post("/episodes/from-articles", response_model=EpisodeResponse, status_code=201)
async def create_episode_from_articles(
    body: EpisodeFromArticles,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    """Create an episode from pre-supplied articles (skips collection step)."""
    if not body.articles:
        raise HTTPException(status_code=400, detail="At least one article is required")

    articles = [a.model_dump() for a in body.articles]
    episode = await engine.create_episode_from_articles(body.title, articles, session)
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


@router.delete("/episodes/{episode_id}", status_code=204)
async def delete_episode(
    episode_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an episode and all related data (news items, steps, API usage, media files)."""
    result = await session.execute(
        select(Episode).where(Episode.id == episode_id).options(selectinload(Episode.pipeline_steps))
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    # Block deletion if any step is running
    for step in episode.pipeline_steps:
        if step.status == StepStatus.RUNNING:
            raise HTTPException(status_code=409, detail=f"Cannot delete: step '{step.step_name.value}' is running")

    # Delete media files
    media_dir = os.path.join(settings.media_dir, str(episode_id))
    if os.path.isdir(media_dir):
        shutil.rmtree(media_dir)

    # Cascade delete handles news_items, pipeline_steps, api_usages
    await session.delete(episode)
    await session.commit()


@router.get(
    "/episodes/{episode_id}/news-items",
    response_model=list[NewsItemResponse],
)
async def get_news_items(
    episode_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[NewsItem]:
    """Get all news items for an episode."""
    result = await session.execute(
        select(NewsItem)
        .where(NewsItem.episode_id == episode_id)
        .order_by(NewsItem.id)
    )
    return list(result.scalars().all())
