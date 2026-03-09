"""Cost statistics API endpoints."""

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import ApiUsage

router = APIRouter(tags=["stats"])


# --- Schemas ---


class CostByProvider(BaseModel):
    """Cost breakdown by provider."""

    provider: str
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    request_count: int


class CostByStep(BaseModel):
    """Cost breakdown by pipeline step."""

    step_name: str
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    request_count: int


class CostStatsResponse(BaseModel):
    """Overall cost statistics."""

    by_provider: list[CostByProvider]
    by_step: list[CostByStep]
    total_cost_usd: float
    total_requests: int


class EpisodeCostResponse(BaseModel):
    """Cost statistics for a single episode."""

    episode_id: int
    by_step: list[CostByStep]
    total_cost_usd: float
    total_requests: int


# --- Endpoints ---


def _apply_date_filter(query, from_date: date | None, to_date: date | None):
    """Apply date range filter to a query."""
    if from_date:
        query = query.where(ApiUsage.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        query = query.where(ApiUsage.created_at <= datetime.combine(to_date, time.max))
    return query


@router.get("/stats/costs", response_model=CostStatsResponse)
async def get_cost_stats(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get overall cost statistics grouped by provider and step.

    Optional date range filter: ?from=2026-03-01&to=2026-03-31
    """
    # By provider
    provider_query = select(
        ApiUsage.provider,
        func.sum(ApiUsage.input_tokens).label("total_input_tokens"),
        func.sum(ApiUsage.output_tokens).label("total_output_tokens"),
        func.sum(ApiUsage.cost_usd).label("total_cost_usd"),
        func.count().label("request_count"),
    ).group_by(ApiUsage.provider)
    provider_result = await session.execute(_apply_date_filter(provider_query, from_date, to_date))
    by_provider = [
        CostByProvider(
            provider=row.provider,
            total_input_tokens=row.total_input_tokens or 0,
            total_output_tokens=row.total_output_tokens or 0,
            total_cost_usd=row.total_cost_usd or 0.0,
            request_count=row.request_count,
        )
        for row in provider_result.all()
    ]

    # By step
    step_query = select(
        ApiUsage.step_name,
        func.sum(ApiUsage.input_tokens).label("total_input_tokens"),
        func.sum(ApiUsage.output_tokens).label("total_output_tokens"),
        func.sum(ApiUsage.cost_usd).label("total_cost_usd"),
        func.count().label("request_count"),
    ).group_by(ApiUsage.step_name)
    step_result = await session.execute(_apply_date_filter(step_query, from_date, to_date))
    by_step = [
        CostByStep(
            step_name=row.step_name,
            total_input_tokens=row.total_input_tokens or 0,
            total_output_tokens=row.total_output_tokens or 0,
            total_cost_usd=row.total_cost_usd or 0.0,
            request_count=row.request_count,
        )
        for row in step_result.all()
    ]

    # Totals
    total_query = select(
        func.sum(ApiUsage.cost_usd).label("total_cost"),
        func.count().label("total_requests"),
    )
    total_result = await session.execute(_apply_date_filter(total_query, from_date, to_date))
    totals = total_result.one()

    return {
        "by_provider": by_provider,
        "by_step": by_step,
        "total_cost_usd": totals.total_cost or 0.0,
        "total_requests": totals.total_requests,
    }


@router.get("/stats/costs/episodes/{episode_id}", response_model=EpisodeCostResponse)
async def get_episode_costs(
    episode_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get cost statistics for a specific episode."""
    step_result = await session.execute(
        select(
            ApiUsage.step_name,
            func.sum(ApiUsage.input_tokens).label("total_input_tokens"),
            func.sum(ApiUsage.output_tokens).label("total_output_tokens"),
            func.sum(ApiUsage.cost_usd).label("total_cost_usd"),
            func.count().label("request_count"),
        )
        .where(ApiUsage.episode_id == episode_id)
        .group_by(ApiUsage.step_name)
    )
    by_step = [
        CostByStep(
            step_name=row.step_name,
            total_input_tokens=row.total_input_tokens or 0,
            total_output_tokens=row.total_output_tokens or 0,
            total_cost_usd=row.total_cost_usd or 0.0,
            request_count=row.request_count,
        )
        for row in step_result.all()
    ]

    total_result = await session.execute(
        select(
            func.sum(ApiUsage.cost_usd).label("total_cost"),
            func.count().label("total_requests"),
        ).where(ApiUsage.episode_id == episode_id)
    )
    totals = total_result.one()

    return {
        "episode_id": episode_id,
        "by_step": by_step,
        "total_cost_usd": totals.total_cost or 0.0,
        "total_requests": totals.total_requests,
    }
