"""HTTP client for AI News Radio FastAPI backend."""

from typing import Any

import httpx

from mcp_server.config import BACKEND_URL, REQUEST_TIMEOUT


class APIError(Exception):
    """API call failed with a meaningful message."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class AINewsRadioClient:
    """Async HTTP client wrapping the FastAPI backend API."""

    def __init__(self, base_url: str = BACKEND_URL, timeout: float = REQUEST_TIMEOUT) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an HTTP request and return parsed JSON."""
        async with self._client() as client:
            response = await client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise APIError(response.status_code, detail)
        if response.status_code == 204:
            return None
        return response.json()

    # ---- Health ----

    async def health(self) -> dict:
        """GET /api/health"""
        return await self._request("GET", "/api/health")

    # ---- Episodes ----

    async def create_episode(self, title: str) -> dict:
        """POST /api/episodes"""
        return await self._request("POST", "/api/episodes", json={"title": title})

    async def create_episode_from_articles(self, title: str, articles: list[dict]) -> dict:
        """POST /api/episodes/from-articles"""
        return await self._request("POST", "/api/episodes/from-articles", json={"title": title, "articles": articles})

    async def list_episodes(self) -> dict:
        """GET /api/episodes"""
        return await self._request("GET", "/api/episodes")

    async def get_episode(self, episode_id: int) -> dict:
        """GET /api/episodes/{episode_id}"""
        return await self._request("GET", f"/api/episodes/{episode_id}")

    async def delete_episode(self, episode_id: int) -> None:
        """DELETE /api/episodes/{episode_id}"""
        await self._request("DELETE", f"/api/episodes/{episode_id}")

    async def get_news_items(self, episode_id: int) -> list[dict]:
        """GET /api/episodes/{episode_id}/news-items"""
        return await self._request("GET", f"/api/episodes/{episode_id}/news-items")

    # ---- Pipeline ----

    async def get_steps(self, episode_id: int) -> list[dict]:
        """GET /api/episodes/{episode_id}/steps"""
        return await self._request("GET", f"/api/episodes/{episode_id}/steps")

    async def run_step(self, episode_id: int, step_name: str, queries: list[str] | None = None) -> dict:
        """POST /api/episodes/{episode_id}/steps/{step_name}/run"""
        body = {}
        if queries:
            body["queries"] = queries
        return await self._request("POST", f"/api/episodes/{episode_id}/steps/{step_name}/run", json=body)

    async def approve_step(self, step_id: int) -> dict:
        """POST /api/steps/{step_id}/approve"""
        return await self._request("POST", f"/api/steps/{step_id}/approve")

    async def reject_step(self, step_id: int, reason: str) -> dict:
        """POST /api/steps/{step_id}/reject"""
        return await self._request("POST", f"/api/steps/{step_id}/reject", json={"reason": reason})

    # ---- Step ID resolution ----

    async def resolve_step_id(self, episode_id: int, step_name: str) -> int:
        """Find the step_id for a given episode_id + step_name."""
        steps = await self.get_steps(episode_id)
        for step in steps:
            if step["step_name"] == step_name:
                return step["id"]
        raise APIError(404, f"Step '{step_name}' not found for episode {episode_id}")

    # ---- Stats ----

    async def get_cost_stats(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        """GET /api/stats/costs"""
        params: dict[str, str] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await self._request("GET", "/api/stats/costs", params=params)

    async def get_episode_cost(self, episode_id: int) -> dict:
        """GET /api/stats/costs/episodes/{episode_id}"""
        return await self._request("GET", f"/api/stats/costs/episodes/{episode_id}")

    # ---- Search ----

    async def search_news(self, query: str, count: int = 10, freshness: str | None = None) -> list[dict]:
        """GET /api/search/news"""
        params: dict[str, Any] = {"q": query, "count": count}
        if freshness:
            params["freshness"] = freshness
        return await self._request("GET", "/api/search/news", params=params)
