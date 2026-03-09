"""Model pricing management API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import ModelPricing

router = APIRouter(tags=["pricing"])


# --- Schemas ---


class PricingResponse(BaseModel):
    """Response for a single model pricing entry."""

    id: int
    model_prefix: str
    provider: str
    input_price_per_1m: float
    output_price_per_1m: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PricingCreate(BaseModel):
    """Request body for creating/updating a pricing entry."""

    model_prefix: str
    provider: str
    input_price_per_1m: float
    output_price_per_1m: float


# --- Endpoints ---


@router.get("/pricing", response_model=list[PricingResponse])
async def list_pricing(
    session: AsyncSession = Depends(get_session),
) -> list[ModelPricing]:
    """List all model pricing entries."""
    result = await session.execute(
        select(ModelPricing).order_by(ModelPricing.provider, ModelPricing.model_prefix)
    )
    return list(result.scalars().all())


@router.post("/pricing", response_model=PricingResponse, status_code=201)
async def create_pricing(
    body: PricingCreate,
    session: AsyncSession = Depends(get_session),
) -> ModelPricing:
    """Create a new model pricing entry."""
    # Check for duplicate
    result = await session.execute(
        select(ModelPricing).where(ModelPricing.model_prefix == body.model_prefix)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Pricing for '{body.model_prefix}' already exists")

    pricing = ModelPricing(
        model_prefix=body.model_prefix,
        provider=body.provider,
        input_price_per_1m=body.input_price_per_1m,
        output_price_per_1m=body.output_price_per_1m,
    )
    session.add(pricing)
    await session.commit()
    await session.refresh(pricing)
    return pricing


@router.put("/pricing/{pricing_id}", response_model=PricingResponse)
async def update_pricing(
    pricing_id: int,
    body: PricingCreate,
    session: AsyncSession = Depends(get_session),
) -> ModelPricing:
    """Update a model pricing entry."""
    result = await session.execute(
        select(ModelPricing).where(ModelPricing.id == pricing_id)
    )
    pricing = result.scalar_one_or_none()
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing entry not found")

    pricing.model_prefix = body.model_prefix
    pricing.provider = body.provider
    pricing.input_price_per_1m = body.input_price_per_1m
    pricing.output_price_per_1m = body.output_price_per_1m
    await session.commit()
    await session.refresh(pricing)
    return pricing


@router.delete("/pricing/{pricing_id}", status_code=204)
async def delete_pricing(
    pricing_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a model pricing entry."""
    result = await session.execute(
        select(ModelPricing).where(ModelPricing.id == pricing_id)
    )
    pricing = result.scalar_one_or_none()
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing entry not found")

    await session.delete(pricing)
    await session.commit()
