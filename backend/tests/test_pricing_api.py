"""Tests for pricing management API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelPricing


class TestPricingAPI:
    async def test_list_pricing_empty(self, client: AsyncClient):
        response = await client.get("/api/pricing")
        assert response.status_code == 200
        assert response.json() == []

    async def test_create_pricing(self, client: AsyncClient):
        response = await client.post(
            "/api/pricing",
            json={
                "model_prefix": "gpt-5",
                "provider": "openai",
                "input_price_per_1m": 1.25,
                "output_price_per_1m": 10.00,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["model_prefix"] == "gpt-5"
        assert data["input_price_per_1m"] == 1.25

    async def test_create_duplicate_returns_409(self, client: AsyncClient):
        body = {
            "model_prefix": "gpt-5",
            "provider": "openai",
            "input_price_per_1m": 1.25,
            "output_price_per_1m": 10.00,
        }
        await client.post("/api/pricing", json=body)
        response = await client.post("/api/pricing", json=body)
        assert response.status_code == 409

    async def test_update_pricing(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/pricing",
            json={
                "model_prefix": "gpt-5",
                "provider": "openai",
                "input_price_per_1m": 1.25,
                "output_price_per_1m": 10.00,
            },
        )
        pricing_id = create_resp.json()["id"]

        update_resp = await client.put(
            f"/api/pricing/{pricing_id}",
            json={
                "model_prefix": "gpt-5",
                "provider": "openai",
                "input_price_per_1m": 1.50,
                "output_price_per_1m": 12.00,
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["input_price_per_1m"] == 1.50

    async def test_delete_pricing(self, client: AsyncClient):
        create_resp = await client.post(
            "/api/pricing",
            json={
                "model_prefix": "gpt-5",
                "provider": "openai",
                "input_price_per_1m": 1.25,
                "output_price_per_1m": 10.00,
            },
        )
        pricing_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/pricing/{pricing_id}")
        assert delete_resp.status_code == 204

        list_resp = await client.get("/api/pricing")
        assert list_resp.json() == []

    async def test_delete_not_found(self, client: AsyncClient):
        response = await client.delete("/api/pricing/999")
        assert response.status_code == 404
