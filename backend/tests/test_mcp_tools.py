"""Tests for MCP server tools, client, and response formatting."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp_server.client import AINewsRadioClient, APIError
from mcp_server.server import _dispatch
from mcp_server.tools import STEP_NAMES, get_tool_definitions


class TestToolDefinitions:
    """Validate MCP tool definitions."""

    def test_tool_count(self):
        tools = get_tool_definitions()
        assert len(tools) == 11

    def test_tool_names(self):
        tools = get_tool_definitions()
        names = {t.name for t in tools}
        expected = {
            "create_episode",
            "create_episode_from_articles",
            "list_episodes",
            "get_episode_status",
            "run_step",
            "approve_step",
            "reject_step",
            "get_step_detail",
            "search_news",
            "get_cost_stats",
            "health_check",
        }
        assert names == expected

    def test_all_tools_have_input_schema(self):
        tools = get_tool_definitions()
        for tool in tools:
            assert tool.inputSchema is not None
            assert tool.inputSchema["type"] == "object"

    def test_required_fields(self):
        tools = get_tool_definitions()
        tool_map = {t.name: t for t in tools}

        # create_episode requires title
        assert tool_map["create_episode"].inputSchema["required"] == ["title"]

        # run_step requires episode_id and step_name
        assert set(tool_map["run_step"].inputSchema["required"]) == {"episode_id", "step_name"}

        # reject_step requires reason
        assert "reason" in tool_map["reject_step"].inputSchema["required"]

        # search_news requires query
        assert tool_map["search_news"].inputSchema["required"] == ["query"]

    def test_step_names_enum_in_run_step(self):
        tools = get_tool_definitions()
        tool_map = {t.name: t for t in tools}
        run_step = tool_map["run_step"]
        step_enum = run_step.inputSchema["properties"]["step_name"]["enum"]
        assert step_enum == STEP_NAMES

    def test_annotations_present(self):
        tools = get_tool_definitions()
        for tool in tools:
            assert tool.annotations is not None

    def test_readonly_tools(self):
        tools = get_tool_definitions()
        tool_map = {t.name: t for t in tools}
        readonly_tools = [
            "list_episodes",
            "get_episode_status",
            "get_step_detail",
            "search_news",
            "get_cost_stats",
            "health_check",
        ]
        for name in readonly_tools:
            assert tool_map[name].annotations.readOnlyHint is True


class TestClient:
    """Test AINewsRadioClient HTTP calls."""

    @pytest.fixture
    def api_client(self):
        return AINewsRadioClient(base_url="http://test:8000")

    async def test_health(self, api_client):
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"status": "ok"}
            result = await api_client.health()
            mock.assert_called_once_with("GET", "/api/health")
            assert result == {"status": "ok"}

    async def test_create_episode(self, api_client):
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"id": 1, "title": "Test", "status": "draft", "pipeline_steps": []}
            result = await api_client.create_episode("Test")
            mock.assert_called_once_with("POST", "/api/episodes", json={"title": "Test"})
            assert result["id"] == 1

    async def test_create_episode_from_articles(self, api_client):
        articles = [{"title": "A", "source_url": "http://a.com", "source_name": "A"}]
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"id": 1, "title": "Test", "status": "in_progress", "pipeline_steps": []}
            await api_client.create_episode_from_articles("Test", articles)
            mock.assert_called_once_with(
                "POST", "/api/episodes/from-articles", json={"title": "Test", "articles": articles}
            )

    async def test_list_episodes(self, api_client):
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"episodes": [], "total": 0}
            result = await api_client.list_episodes()
            mock.assert_called_once_with("GET", "/api/episodes")
            assert result["total"] == 0

    async def test_run_step(self, api_client):
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"id": 1, "step_name": "collection", "status": "running"}
            await api_client.run_step(1, "collection")
            mock.assert_called_once_with("POST", "/api/episodes/1/steps/collection/run", json={})

    async def test_run_step_with_queries(self, api_client):
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"id": 1, "step_name": "collection", "status": "running"}
            await api_client.run_step(1, "collection", queries=["熊本 ニュース"])
            mock.assert_called_once_with(
                "POST", "/api/episodes/1/steps/collection/run", json={"queries": ["熊本 ニュース"]}
            )

    async def test_approve_step(self, api_client):
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"id": 5, "step_name": "collection", "status": "approved"}
            await api_client.approve_step(5)
            mock.assert_called_once_with("POST", "/api/steps/5/approve")

    async def test_reject_step(self, api_client):
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"id": 5, "step_name": "collection", "status": "rejected"}
            await api_client.reject_step(5, "Bad quality")
            mock.assert_called_once_with("POST", "/api/steps/5/reject", json={"reason": "Bad quality"})

    async def test_resolve_step_id(self, api_client):
        with patch.object(api_client, "get_steps", new_callable=AsyncMock) as mock:
            mock.return_value = [
                {"id": 10, "step_name": "collection", "status": "approved"},
                {"id": 11, "step_name": "factcheck", "status": "pending"},
            ]
            step_id = await api_client.resolve_step_id(1, "factcheck")
            assert step_id == 11

    async def test_resolve_step_id_not_found(self, api_client):
        with patch.object(api_client, "get_steps", new_callable=AsyncMock) as mock:
            mock.return_value = [{"id": 10, "step_name": "collection", "status": "approved"}]
            with pytest.raises(APIError, match="not found"):
                await api_client.resolve_step_id(1, "nonexistent")

    async def test_get_cost_stats(self, api_client):
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"total_cost_usd": 0.5, "total_requests": 10, "by_provider": [], "by_step": []}
            await api_client.get_cost_stats("2026-01-01", "2026-03-01")
            mock.assert_called_once_with(
                "GET", "/api/stats/costs", params={"from": "2026-01-01", "to": "2026-03-01"}
            )

    async def test_search_news(self, api_client):
        with patch.object(api_client, "_request", new_callable=AsyncMock) as mock:
            mock.return_value = [{"title": "News", "url": "http://test.com", "description": "Desc", "age": "1h"}]
            await api_client.search_news("熊本", count=5, freshness="pd")
            mock.assert_called_once_with(
                "GET", "/api/search/news", params={"q": "熊本", "count": 5, "freshness": "pd"}
            )


class TestDispatch:
    """Test server dispatch and response formatting."""

    async def test_health_check(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.health = AsyncMock(return_value={"status": "ok"})
            result = await _dispatch("health_check", {})
            assert "ok" in result

    async def test_create_episode(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.create_episode = AsyncMock(
                return_value={
                    "id": 1,
                    "title": "Test Episode",
                    "status": "draft",
                    "pipeline_steps": [
                        {"step_name": "collection", "status": "pending"},
                        {"step_name": "factcheck", "status": "pending"},
                    ],
                }
            )
            result = await _dispatch("create_episode", {"title": "Test Episode"})
            assert "Episode #1 created" in result
            assert "Test Episode" in result
            assert "collection" in result

    async def test_list_episodes_empty(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.list_episodes = AsyncMock(return_value={"episodes": [], "total": 0})
            result = await _dispatch("list_episodes", {})
            assert "No episodes found" in result

    async def test_list_episodes(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.list_episodes = AsyncMock(
                return_value={
                    "episodes": [
                        {
                            "id": 1,
                            "title": "Ep 1",
                            "status": "in_progress",
                            "pipeline_steps": [
                                {"step_name": "collection", "status": "approved"},
                                {"step_name": "factcheck", "status": "running"},
                            ],
                        }
                    ],
                    "total": 1,
                }
            )
            result = await _dispatch("list_episodes", {})
            assert "#1" in result
            assert "Ep 1" in result
            assert "in_progress" in result

    async def test_get_episode_status(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.get_episode = AsyncMock(
                return_value={
                    "id": 1,
                    "title": "Test",
                    "status": "in_progress",
                    "created_at": "2026-03-09T00:00:00",
                    "pipeline_steps": [
                        {"step_name": "collection", "status": "approved", "started_at": "t1", "completed_at": "t2", "rejection_reason": None},
                    ],
                }
            )
            mock_client.get_news_items = AsyncMock(
                return_value=[
                    {
                        "title": "News 1",
                        "source_name": "NHK",
                        "source_url": "http://nhk.or.jp/1",
                        "fact_check_score": 4,
                        "script_text": None,
                    }
                ]
            )
            result = await _dispatch("get_episode_status", {"episode_id": 1})
            assert "Episode #1" in result
            assert "collection" in result
            assert "[v]" in result
            assert "News 1" in result
            assert "fact-check: 4/5" in result

    async def test_run_step(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.run_step = AsyncMock(
                return_value={"id": 1, "step_name": "collection", "status": "running"}
            )
            result = await _dispatch("run_step", {"episode_id": 1, "step_name": "collection"})
            assert "started" in result
            assert "get_episode_status" in result

    async def test_approve_step(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.resolve_step_id = AsyncMock(return_value=5)
            mock_client.approve_step = AsyncMock(
                return_value={"id": 5, "step_name": "collection", "status": "approved"}
            )
            result = await _dispatch("approve_step", {"episode_id": 1, "step_name": "collection"})
            assert "approved" in result
            assert "factcheck" in result  # next step hint

    async def test_approve_last_step(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.resolve_step_id = AsyncMock(return_value=7)
            mock_client.approve_step = AsyncMock(
                return_value={"id": 7, "step_name": "publish", "status": "approved"}
            )
            result = await _dispatch("approve_step", {"episode_id": 1, "step_name": "publish"})
            assert "final step" in result

    async def test_reject_step(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.resolve_step_id = AsyncMock(return_value=5)
            mock_client.reject_step = AsyncMock(
                return_value={"id": 5, "step_name": "factcheck", "status": "rejected"}
            )
            result = await _dispatch("reject_step", {"episode_id": 1, "step_name": "factcheck", "reason": "Low quality"})
            assert "rejected" in result
            assert "Low quality" in result

    async def test_search_news(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.search_news = AsyncMock(
                return_value=[
                    {"title": "熊本ニュース1", "url": "http://example.com/1", "description": "Description 1", "age": "2h"},
                    {"title": "熊本ニュース2", "url": "http://example.com/2", "description": "Description 2", "age": None},
                ]
            )
            result = await _dispatch("search_news", {"query": "熊本"})
            assert "熊本ニュース1" in result
            assert "http://example.com/1" in result
            assert "2 results" in result

    async def test_search_news_empty(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.search_news = AsyncMock(return_value=[])
            result = await _dispatch("search_news", {"query": "nonexistent"})
            assert "No results" in result

    async def test_get_cost_stats(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.get_cost_stats = AsyncMock(
                return_value={
                    "total_cost_usd": 1.2345,
                    "total_requests": 42,
                    "by_provider": [{"provider": "anthropic", "total_cost_usd": 1.0, "request_count": 30}],
                    "by_step": [{"step_name": "factcheck", "total_cost_usd": 0.5, "request_count": 10}],
                }
            )
            result = await _dispatch("get_cost_stats", {})
            assert "$1.2345" in result
            assert "42 requests" in result
            assert "anthropic" in result
            assert "factcheck" in result

    async def test_get_cost_stats_by_episode(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.get_episode_cost = AsyncMock(
                return_value={
                    "episode_id": 1,
                    "total_cost_usd": 0.5,
                    "total_requests": 10,
                    "by_provider": [],
                    "by_step": [],
                }
            )
            result = await _dispatch("get_cost_stats", {"episode_id": 1})
            assert "Episode #1" in result
            assert "$0.5000" in result

    async def test_get_step_detail(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.get_steps = AsyncMock(
                return_value=[
                    {
                        "step_name": "collection",
                        "status": "needs_approval",
                        "started_at": "2026-03-09T01:00:00",
                        "completed_at": "2026-03-09T01:05:00",
                        "input_data": {"queries": ["熊本"]},
                        "output_data": {"articles_found": 5},
                        "rejection_reason": None,
                    }
                ]
            )
            result = await _dispatch("get_step_detail", {"episode_id": 1, "step_name": "collection"})
            assert "collection" in result
            assert "needs_approval" in result
            assert "熊本" in result
            assert "articles_found" in result

    async def test_get_step_detail_not_found(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.get_steps = AsyncMock(return_value=[])
            result = await _dispatch("get_step_detail", {"episode_id": 1, "step_name": "collection"})
            assert "not found" in result

    async def test_unknown_tool(self):
        result = await _dispatch("nonexistent_tool", {})
        assert "Unknown tool" in result


class TestErrorHandling:
    """Test error handling in dispatch."""

    async def test_api_error_returned_as_text(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.health = AsyncMock(side_effect=APIError(500, "Internal Server Error"))
            from mcp_server.server import call_tool

            result = await call_tool("health_check", {})
            assert len(result) == 1
            assert "Internal Server Error" in result[0].text

    async def test_unexpected_error(self):
        with patch("mcp_server.server.client") as mock_client:
            mock_client.health = AsyncMock(side_effect=RuntimeError("unexpected"))
            from mcp_server.server import call_tool

            result = await call_tool("health_check", {})
            assert len(result) == 1
            assert "unexpected" in result[0].text


class TestSearchAPI:
    """Test the search API endpoint via FastAPI test client."""

    async def test_search_news_endpoint(self, client):
        with patch("app.api.search.BraveSearchService") as mock_cls:
            mock_service = AsyncMock()
            mock_cls.return_value = mock_service

            from app.services.brave_search import BraveSearchResult

            mock_service.web_search.return_value = [
                BraveSearchResult(title="Test", url="http://test.com", description="Desc", age="1h")
            ]

            response = await client.get("/api/search/news", params={"q": "test", "count": 5})
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["title"] == "Test"
            assert data[0]["url"] == "http://test.com"
            mock_service.web_search.assert_called_once_with(query="test", count=5, freshness=None)

    async def test_search_news_missing_query(self, client):
        response = await client.get("/api/search/news")
        assert response.status_code == 422

    async def test_search_news_with_freshness(self, client):
        with patch("app.api.search.BraveSearchService") as mock_cls:
            mock_service = AsyncMock()
            mock_cls.return_value = mock_service
            mock_service.web_search.return_value = []

            response = await client.get("/api/search/news", params={"q": "test", "freshness": "pd"})
            assert response.status_code == 200
            mock_service.web_search.assert_called_once_with(query="test", count=10, freshness="pd")

    async def test_search_news_invalid_freshness(self, client):
        response = await client.get("/api/search/news", params={"q": "test", "freshness": "invalid"})
        assert response.status_code == 422
