"""News search API endpoint using Brave Search and YouTube Data API."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.brave_search import BraveSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


class SearchResultResponse(BaseModel):
    """A single search result."""

    title: str
    url: str
    description: str
    age: str | None = None


@router.get("/news", response_model=list[SearchResultResponse])
async def search_news(
    q: str = Query(..., description="Search query"),
    count: int = Query(10, ge=1, le=20, description="Number of results"),
    freshness: str | None = Query(None, pattern="^(pd|pw|pm)$", description="Time filter: pd/pw/pm"),
    source: str = Query("brave", pattern="^(brave|youtube)$", description="Search source: brave or youtube"),
) -> list[SearchResultResponse]:
    """Search for news articles using Brave Search or YouTube Data API."""
    if source == "youtube":
        return await _search_youtube(q, count)
    return await _search_brave(q, count, freshness)


async def _search_brave(
    q: str, count: int, freshness: str | None
) -> list[SearchResultResponse]:
    """Search using Brave Search API."""
    try:
        service = BraveSearchService()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    results = await service.web_search(query=q, count=count, freshness=freshness)
    return [
        SearchResultResponse(
            title=r.title,
            url=r.url,
            description=r.description,
            age=r.age,
        )
        for r in results
    ]


async def _search_youtube(q: str, count: int) -> list[SearchResultResponse]:
    """Search using YouTube Data API v3."""
    from app.config import settings
    from app.services.youtube_search import YouTubeSearchService

    try:
        service = YouTubeSearchService()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    results = await service.search(
        query=q,
        max_results=count,
        order=settings.collection_youtube_search_order,
        region_code=settings.collection_youtube_search_region,
        relevance_language=settings.collection_youtube_search_language,
    )
    return [
        SearchResultResponse(
            title=r.title,
            url=r.url,
            description=f"[{r.channel_name}] {r.description}",
            age=r.published_at,
        )
        for r in results
    ]
