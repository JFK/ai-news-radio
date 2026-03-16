"""Speaker profiles CRUD API."""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.speaker_profile import SpeakerProfile

router = APIRouter(tags=["speakers"])


class SpeakerCreate(BaseModel):
    """Request body for creating/updating a speaker profile."""

    name: str
    role: str
    voice_name: str = "Kore"
    voice_instructions: str = ""
    avatar_position: str = "right"
    description: str = ""


class SpeakerResponse(BaseModel):
    """Response for a speaker profile."""

    id: int
    name: str
    role: str
    voice_name: str
    voice_instructions: str
    avatar_path: str | None
    avatar_position: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.get("/speakers")
async def list_speakers(session: AsyncSession = Depends(get_session)) -> list[SpeakerResponse]:
    """List all speaker profiles."""
    result = await session.execute(select(SpeakerProfile).order_by(SpeakerProfile.id))
    return [SpeakerResponse.model_validate(s) for s in result.scalars()]


@router.post("/speakers")
async def create_speaker(
    body: SpeakerCreate, session: AsyncSession = Depends(get_session)
) -> SpeakerResponse:
    """Create a new speaker profile."""
    # Validate role uniqueness
    existing = await session.execute(
        select(SpeakerProfile).where(SpeakerProfile.role == body.role)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Role '{body.role}' is already assigned to another speaker")

    speaker = SpeakerProfile(
        name=body.name,
        role=body.role,
        voice_name=body.voice_name,
        voice_instructions=body.voice_instructions,
        avatar_position=body.avatar_position,
        description=body.description,
    )
    session.add(speaker)
    await session.commit()
    await session.refresh(speaker)
    return SpeakerResponse.model_validate(speaker)


@router.put("/speakers/{speaker_id}")
async def update_speaker(
    speaker_id: int, body: SpeakerCreate, session: AsyncSession = Depends(get_session)
) -> SpeakerResponse:
    """Update an existing speaker profile."""
    result = await session.execute(select(SpeakerProfile).where(SpeakerProfile.id == speaker_id))
    speaker = result.scalar_one_or_none()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    # Validate role uniqueness (exclude self)
    existing = await session.execute(
        select(SpeakerProfile).where(
            SpeakerProfile.role == body.role, SpeakerProfile.id != speaker_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Role '{body.role}' is already assigned to another speaker")

    speaker.name = body.name
    speaker.role = body.role
    speaker.voice_name = body.voice_name
    speaker.voice_instructions = body.voice_instructions
    speaker.avatar_position = body.avatar_position
    speaker.description = body.description
    await session.commit()
    await session.refresh(speaker)
    return SpeakerResponse.model_validate(speaker)


@router.delete("/speakers/{speaker_id}")
async def delete_speaker(
    speaker_id: int, session: AsyncSession = Depends(get_session)
) -> dict:
    """Delete a speaker profile."""
    result = await session.execute(select(SpeakerProfile).where(SpeakerProfile.id == speaker_id))
    speaker = result.scalar_one_or_none()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    await session.delete(speaker)
    await session.commit()
    return {"deleted": True}


@router.post("/speakers/{speaker_id}/avatar")
async def upload_avatar(
    speaker_id: int,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
) -> SpeakerResponse:
    """Upload an avatar image for a speaker."""
    result = await session.execute(select(SpeakerProfile).where(SpeakerProfile.id == speaker_id))
    speaker = result.scalar_one_or_none()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted")

    avatar_dir = os.path.join(settings.media_dir, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    avatar_path = os.path.join(avatar_dir, f"speaker_{speaker_id}.png")

    content = await file.read()
    with open(avatar_path, "wb") as f:
        f.write(content)

    speaker.avatar_path = avatar_path
    await session.commit()
    await session.refresh(speaker)
    return SpeakerResponse.model_validate(speaker)


@router.delete("/speakers/{speaker_id}/avatar")
async def delete_avatar(
    speaker_id: int,
    session: AsyncSession = Depends(get_session),
) -> SpeakerResponse:
    """Remove avatar from a speaker."""
    result = await session.execute(select(SpeakerProfile).where(SpeakerProfile.id == speaker_id))
    speaker = result.scalar_one_or_none()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    if speaker.avatar_path and os.path.exists(speaker.avatar_path):
        os.remove(speaker.avatar_path)

    speaker.avatar_path = None
    await session.commit()
    await session.refresh(speaker)
    return SpeakerResponse.model_validate(speaker)
