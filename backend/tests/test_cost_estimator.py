"""Tests for cost estimation service."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelPricing
from app.services.cost_estimator import estimate_cost


async def _seed_pricing(session: AsyncSession) -> None:
    """Insert test pricing data."""
    entries = [
        ModelPricing(model_prefix="gpt-5", provider="openai", input_price_per_1m=1.25, output_price_per_1m=10.00),
        ModelPricing(model_prefix="gpt-4o-mini", provider="openai", input_price_per_1m=0.15, output_price_per_1m=0.60),
        ModelPricing(model_prefix="claude-sonnet-4-5", provider="anthropic", input_price_per_1m=3.00, output_price_per_1m=15.00),
    ]
    session.add_all(entries)
    await session.commit()


class TestEstimateCost:
    async def test_exact_match(self, session: AsyncSession):
        await _seed_pricing(session)
        cost = await estimate_cost(session, "gpt-5", 1_000_000, 1_000_000)
        assert cost == pytest.approx(11.25)  # 1.25 + 10.00

    async def test_prefix_match(self, session: AsyncSession):
        await _seed_pricing(session)
        cost = await estimate_cost(session, "gpt-5-2025-01-15", 1_000_000, 0)
        assert cost == pytest.approx(1.25)

    async def test_unknown_model_returns_zero(self, session: AsyncSession):
        await _seed_pricing(session)
        cost = await estimate_cost(session, "unknown-model", 1_000_000, 1_000_000)
        assert cost == 0.0

    async def test_zero_tokens(self, session: AsyncSession):
        await _seed_pricing(session)
        cost = await estimate_cost(session, "gpt-5", 0, 0)
        assert cost == 0.0

    async def test_small_token_count(self, session: AsyncSession):
        await _seed_pricing(session)
        # 1000 input tokens of gpt-4o-mini: 1000 * 0.15 / 1M = 0.00015
        cost = await estimate_cost(session, "gpt-4o-mini", 1000, 0)
        assert cost == pytest.approx(0.00015)

    async def test_empty_db_returns_zero(self, session: AsyncSession):
        cost = await estimate_cost(session, "gpt-5", 1_000_000, 1_000_000)
        assert cost == 0.0
