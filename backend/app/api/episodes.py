"""Episode CRUD API endpoints."""

import os
import shutil
from datetime import date

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
from app.services.export_source_text import generate_source_text
from app.services.google_drive import GoogleDriveService
from app.models import Episode, EpisodeStatus, NewsItem, StepStatus
from app.pipeline import engine

router = APIRouter(tags=["episodes"])


# --- Endpoints ---


@router.post("/episodes", response_model=EpisodeResponse, status_code=201)
async def create_episode(
    body: EpisodeCreate,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    """Create a new episode with all 6 pipeline steps."""
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


@router.post("/episodes/{episode_id}/toggle-complete", response_model=EpisodeResponse)
async def toggle_complete(
    episode_id: int,
    session: AsyncSession = Depends(get_session),
) -> Episode:
    """Toggle episode status between in_progress and completed.

    Allows marking an episode as completed even if not all pipeline steps
    are finished (e.g., after exporting analysis to Google Drive).
    """
    result = await session.execute(
        select(Episode).where(Episode.id == episode_id).options(selectinload(Episode.pipeline_steps))
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    if episode.status == EpisodeStatus.COMPLETED:
        episode.status = EpisodeStatus.IN_PROGRESS
    elif episode.status in (EpisodeStatus.IN_PROGRESS, EpisodeStatus.DRAFT):
        episode.status = EpisodeStatus.COMPLETED
    else:
        raise HTTPException(status_code=400, detail=f"Cannot toggle from status: {episode.status.value}")

    await session.commit()
    await session.refresh(episode)
    return await engine.get_episode_with_steps(episode.id, session)


@router.post("/episodes/{episode_id}/export/drive")
async def export_to_drive(
    episode_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Export episode analysis to Google Drive as NotebookLM source text."""
    if not settings.google_drive_enabled:
        raise HTTPException(status_code=400, detail="Google Drive export is not enabled")
    if not settings.google_drive_refresh_token:
        raise HTTPException(status_code=400, detail="Google Drive is not authenticated. Please authenticate via Settings.")

    # Load episode with relationships
    result = await session.execute(
        select(Episode).where(Episode.id == episode_id).options(selectinload(Episode.pipeline_steps))
    )
    episode = result.scalar_one_or_none()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    # Verify analysis step is approved
    analysis_step = next((s for s in episode.pipeline_steps if s.step_name.value == "analysis"), None)
    if not analysis_step or analysis_step.status.value != "approved":
        raise HTTPException(status_code=400, detail="Analysis step must be approved before exporting")

    # Get non-excluded news items with analysis data
    items_result = await session.execute(
        select(NewsItem)
        .where(
            NewsItem.episode_id == episode_id,
            NewsItem.excluded.is_(False),
        )
        .order_by(NewsItem.id)
    )
    news_items = list(items_result.scalars().all())
    if not news_items:
        raise HTTPException(status_code=400, detail="No news items to export")

    # Generate source text
    source_text, input_tokens, output_tokens = await generate_source_text(episode, news_items, session)

    # Upload to Google Drive
    filename = f"ai-news-radio_ep{episode_id}_{date.today().isoformat()}.txt"

    drive_service = GoogleDriveService()

    if episode.drive_file_id:
        # Update existing file
        file_id, file_url = await drive_service.update_text_file(episode.drive_file_id, source_text)
    else:
        # Create new file
        file_id, file_url = await drive_service.upload_text_file(filename, source_text)

    # Update episode
    episode.drive_file_id = file_id
    episode.drive_file_url = file_url
    await session.commit()

    return {
        "episode_id": episode_id,
        "drive_file_id": file_id,
        "drive_file_url": file_url,
        "source_text_length": len(source_text),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
