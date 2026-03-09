"""Pronunciation dictionary API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import PronunciationCreate, PronunciationResponse
from app.database import get_session
from app.models import Pronunciation

router = APIRouter(tags=["dictionary"])


@router.get("/dictionary", response_model=list[PronunciationResponse])
async def list_pronunciations(
    session: AsyncSession = Depends(get_session),
) -> list[Pronunciation]:
    """List all pronunciation dictionary entries."""
    result = await session.execute(select(Pronunciation).order_by(Pronunciation.priority.desc(), Pronunciation.id))
    return list(result.scalars().all())


@router.post("/dictionary", response_model=PronunciationResponse, status_code=201)
async def create_pronunciation(
    body: PronunciationCreate,
    session: AsyncSession = Depends(get_session),
) -> Pronunciation:
    """Add a pronunciation entry."""
    # Check for duplicate surface
    result = await session.execute(select(Pronunciation).where(Pronunciation.surface == body.surface))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Entry for '{body.surface}' already exists")

    entry = Pronunciation(
        surface=body.surface,
        reading=body.reading,
        priority=body.priority,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.delete("/dictionary/{entry_id}", status_code=204)
async def delete_pronunciation(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a pronunciation entry."""
    result = await session.execute(select(Pronunciation).where(Pronunciation.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    await session.delete(entry)
    await session.commit()
