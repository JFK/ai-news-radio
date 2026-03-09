"""Cost estimation service using DB-managed pricing."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_pricing import ModelPricing

logger = logging.getLogger(__name__)


async def estimate_cost(session: AsyncSession, model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate API cost in USD using pricing from the database.

    Tries exact match first, then prefix match (e.g., "gpt-5-2025-01" matches "gpt-5").
    """
    # Try exact match
    result = await session.execute(
        select(ModelPricing).where(ModelPricing.model_prefix == model)
    )
    pricing = result.scalar_one_or_none()

    # Try prefix match
    if pricing is None:
        result = await session.execute(
            select(ModelPricing).order_by(ModelPricing.model_prefix.desc())
        )
        all_pricing = result.scalars().all()
        for p in all_pricing:
            if model.startswith(p.model_prefix):
                pricing = p
                break

    if pricing is None:
        logger.warning("No pricing found for model: %s", model)
        return 0.0

    return (input_tokens * pricing.input_price_per_1m + output_tokens * pricing.output_price_per_1m) / 1_000_000
