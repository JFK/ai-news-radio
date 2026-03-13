"""Brave Search service for news collection and fact-checking."""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_NEWS_SEARCH_URL = "https://api.search.brave.com/res/v1/news/search"


@dataclass
class BraveSearchResult:
    """A single search result from Brave Search."""

    title: str
    url: str
    description: str
    age: str | None = None


BRAVE_COST_PER_QUERY = 0.005  # $5 per 1,000 queries


class BraveSearchService:
    """Brave Search API client for news collection and fact-checking."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.brave_search_api_key
        if not self._api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY is not set")
        self.query_count: int = 0

    async def web_search(
        self,
        query: str,
        count: int = 10,
        freshness: str | None = None,
    ) -> list[BraveSearchResult]:
        """Search the web using Brave Search API.

        Args:
            query: Search query (any language)
            count: Number of results (max 20)
            freshness: Time filter — "pd" (day), "pw" (week), "pm" (month), "py" (year)
        """
        params: dict = {
            "q": query,
            "count": min(count, 20),
        }
        if freshness:
            params["freshness"] = freshness

        return await self._search(BRAVE_WEB_SEARCH_URL, params, "web")

    async def news_search(
        self,
        query: str,
        count: int = 10,
        freshness: str | None = "pd",
    ) -> list[BraveSearchResult]:
        """Search news articles using Brave Search API.

        Note: News API primarily supports English-speaking countries.
        For Japanese news, web_search with freshness filter is recommended.

        Args:
            query: Search query
            count: Number of results (max 20)
            freshness: Time filter (default: "pd" = past day)
        """
        params: dict = {
            "q": query,
            "count": min(count, 20),
        }
        if freshness:
            params["freshness"] = freshness

        return await self._search(BRAVE_NEWS_SEARCH_URL, params, "news")

    async def _search(self, url: str, params: dict, search_type: str) -> list[BraveSearchResult]:
        """Execute a Brave Search API request."""
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        results: list[BraveSearchResult] = []

        if search_type == "web":
            web_results = data.get("web", {}).get("results", [])
            for item in web_results:
                results.append(
                    BraveSearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        description=item.get("description", ""),
                    )
                )
        elif search_type == "news":
            news_results = data.get("results", [])
            for item in news_results:
                results.append(
                    BraveSearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        description=item.get("description", ""),
                        age=item.get("age"),
                    )
                )

        self.query_count += 1
        logger.info("Brave %s search '%s': %d results", search_type, params["q"], len(results))
        return results
