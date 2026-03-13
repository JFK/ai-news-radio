"""Tests for Brave Search service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.brave_search import BRAVE_COST_PER_QUERY, BraveSearchResult, BraveSearchService


class TestBraveSearchService:
    def test_init_raises_without_api_key(self):
        with patch("app.services.brave_search.settings") as mock_settings:
            mock_settings.brave_search_api_key = ""
            with pytest.raises(ValueError, match="BRAVE_SEARCH_API_KEY"):
                BraveSearchService()

    def test_init_with_explicit_key(self):
        service = BraveSearchService(api_key="test-key")
        assert service._api_key == "test-key"

    @patch("app.services.brave_search.httpx.AsyncClient")
    async def test_web_search(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "テスト記事", "url": "https://example.com/1", "description": "テスト説明"},
                    {"title": "テスト記事2", "url": "https://example.com/2", "description": "テスト説明2"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = BraveSearchService(api_key="test-key")
        results = await service.web_search("熊本 ニュース", count=5)

        assert len(results) == 2
        assert results[0].title == "テスト記事"
        assert results[0].url == "https://example.com/1"
        mock_client.get.assert_called_once()

    @patch("app.services.brave_search.httpx.AsyncClient")
    async def test_web_search_with_freshness(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = BraveSearchService(api_key="test-key")
        await service.web_search("test", freshness="pw")

        call_kwargs = mock_client.get.call_args
        assert call_kwargs[1]["params"]["freshness"] == "pw"

    @patch("app.services.brave_search.httpx.AsyncClient")
    async def test_news_search(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "ニュース1", "url": "https://news.example.com/1", "description": "desc", "age": "2h"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = BraveSearchService(api_key="test-key")
        results = await service.news_search("test news")

        assert len(results) == 1
        assert results[0].age == "2h"

    @patch("app.services.brave_search.httpx.AsyncClient")
    async def test_empty_results(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = BraveSearchService(api_key="test-key")
        results = await service.web_search("obscure query")

        assert results == []

    @patch("app.services.brave_search.httpx.AsyncClient")
    async def test_query_count_incremented(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = BraveSearchService(api_key="test-key")
        assert service.query_count == 0

        await service.web_search("query1")
        assert service.query_count == 1

        await service.web_search("query2")
        assert service.query_count == 2

    def test_cost_per_query_constant(self):
        assert BRAVE_COST_PER_QUERY == 0.005
