"""YouTube Data API v3 search service for news collection."""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_COST_PER_QUERY = 0.0  # Free tier (100 units per search, 10000 units/day)


@dataclass
class YouTubeSearchResult:
    """A single search result from YouTube Data API."""

    title: str
    url: str
    description: str
    channel_name: str
    published_at: str | None = None
    video_id: str | None = None


class YouTubeSearchService:
    """YouTube Data API v3 client for video news collection."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.collection_youtube_api_key
        if not self._api_key:
            raise ValueError("COLLECTION_YOUTUBE_API_KEY is not set")
        self.query_count: int = 0

    async def search(
        self,
        query: str,
        max_results: int = 5,
        order: str = "relevance",
        published_after: str | None = None,
        region_code: str = "",
        relevance_language: str = "",
    ) -> list[YouTubeSearchResult]:
        """Search YouTube videos.

        Args:
            query: Search query
            max_results: Max results (1-50)
            order: Sort order — "relevance", "date", "viewCount"
            published_after: RFC 3339 datetime (e.g. "2026-03-01T00:00:00Z")
            region_code: ISO 3166-1 alpha-2 country code (e.g. "JP", "US")
            relevance_language: ISO 639-1 language code (e.g. "ja", "en")
        """
        params: dict = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 50),
            "order": order,
            "key": self._api_key,
        }
        if published_after:
            params["publishedAfter"] = published_after
        if region_code:
            params["regionCode"] = region_code
        if relevance_language:
            params["relevanceLanguage"] = relevance_language

        results: list[YouTubeSearchResult] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(YOUTUBE_SEARCH_URL, params=params)
                response.raise_for_status()
                data = response.json()

            for item in data.get("items", []):
                video_id = item.get("id", {}).get("videoId", "")
                snippet = item.get("snippet", {})
                results.append(
                    YouTubeSearchResult(
                        title=snippet.get("title", ""),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        description=snippet.get("description", ""),
                        channel_name=snippet.get("channelTitle", ""),
                        published_at=snippet.get("publishedAt"),
                        video_id=video_id,
                    )
                )

            self.query_count += 1
            logger.info("YouTube search '%s': %d results", query, len(results))
        except httpx.HTTPStatusError as e:
            logger.error(
                "YouTube API error: %s %s",
                e.response.status_code,
                e.response.text[:200],
            )
            raise
        except Exception as e:
            logger.error("YouTube search failed for '%s': %s", query, e)
            raise

        return results
