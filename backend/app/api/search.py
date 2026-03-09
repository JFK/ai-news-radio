"""News search API endpoint using Brave Search."""

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
) -> list[SearchResultResponse]:
    """Search for news articles using Brave Search."""
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
