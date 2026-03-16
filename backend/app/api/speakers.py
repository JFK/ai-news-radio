"""Speaker profiles CRUD API."""

import glob
import os
import shutil
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


class AvatarGenerateRequest(BaseModel):
    """Request body for AI avatar generation."""

    custom_prompt: str = ""


class AvatarLibraryResponse(BaseModel):
    """Response for avatar library listing."""

    images: list[str]  # List of relative URLs


class AvatarSelectRequest(BaseModel):
    """Request body to select an avatar from the library."""

    image_path: str  # Relative path like "avatars/speaker_1/001.png"


class AvatarGenerateResponse(BaseModel):
    """Response for avatar generation including cost info."""

    speaker: SpeakerResponse
    cost_usd: float = 0.0
    visual_provider: str = ""


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


@router.post("/speakers/{speaker_id}/avatar/generate")
async def generate_avatar(
    speaker_id: int,
    body: AvatarGenerateRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> AvatarGenerateResponse:
    """Generate an AI avatar image for a speaker using Imagen 4."""
    result = await session.execute(select(SpeakerProfile).where(SpeakerProfile.id == speaker_id))
    speaker = result.scalar_one_or_none()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    from app.services.visual_provider import get_visual_provider

    visual = get_visual_provider()

    # Build prompt from speaker profile
    role_desc = {
        "anchor": "a news anchor / TV host",
        "expert": "a news commentator / analyst",
        "narrator": "a radio narrator",
    }.get(speaker.role, "a media personality")

    custom = (body.custom_prompt if body and body.custom_prompt else "").strip()
    if custom:
        # Append safety suffix to user prompts
        prompt = f"{custom}. No text, no letters, no words, no watermarks."
    else:
        prompt = (
            f"Anime-style portrait of {role_desc}, named {speaker.name}. "
            f"Upper body, clean simple background. Friendly and professional expression. "
            f"High quality, detailed illustration. "
            f"No text, no letters, no words, no watermarks."
        )

    # Save to library directory with sequential numbering
    lib_dir = os.path.join(settings.media_dir, "avatars", f"speaker_{speaker_id}")
    os.makedirs(lib_dir, exist_ok=True)

    existing = sorted(glob.glob(os.path.join(lib_dir, "*.png")))
    next_num = len(existing) + 1
    filename = f"{next_num:03d}.png"
    output_path = os.path.join(lib_dir, filename)

    await visual.generate_illustration(prompt, output_path)

    # Record cost in api_usages (use episode_id=0 as a sentinel for non-episode usage)
    cost_usd = 0.04 if settings.visual_provider == "google" else 0.0
    if cost_usd > 0:
        from app.models.api_usage import ApiUsage

        # Find any episode to attach to, or skip if none exist
        from app.models.episode import Episode as EpisodeModel

        ep_result = await session.execute(
            select(EpisodeModel).order_by(EpisodeModel.id.desc()).limit(1)
        )
        latest_ep = ep_result.scalar_one_or_none()
        if latest_ep:
            usage = ApiUsage(
                episode_id=latest_ep.id,
                step_name="avatar",
                provider="google-imagen",
                model=settings.visual_imagen_model,
                input_tokens=0,
                output_tokens=0,
                cost_usd=cost_usd,
            )
            session.add(usage)

    # Auto-select if no avatar set yet
    if not speaker.avatar_path:
        active_path = os.path.join(settings.media_dir, "avatars", f"speaker_{speaker_id}.png")
        shutil.copy2(output_path, active_path)
        speaker.avatar_path = active_path

    await session.commit()
    await session.refresh(speaker)

    return AvatarGenerateResponse(
        speaker=SpeakerResponse.model_validate(speaker),
        cost_usd=cost_usd,
        visual_provider=settings.visual_provider,
    )


@router.get("/speakers/{speaker_id}/avatar/library")
async def get_avatar_library(
    speaker_id: int,
    session: AsyncSession = Depends(get_session),
) -> AvatarLibraryResponse:
    """List all generated avatar images for a speaker."""
    result = await session.execute(select(SpeakerProfile).where(SpeakerProfile.id == speaker_id))
    speaker = result.scalar_one_or_none()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    lib_dir = os.path.join(settings.media_dir, "avatars", f"speaker_{speaker_id}")
    if not os.path.isdir(lib_dir):
        return AvatarLibraryResponse(images=[])

    images = sorted(glob.glob(os.path.join(lib_dir, "*.png")))
    relative = [f"/media/avatars/speaker_{speaker_id}/{os.path.basename(p)}" for p in images]
    return AvatarLibraryResponse(images=relative)


@router.put("/speakers/{speaker_id}/avatar/select")
async def select_avatar(
    speaker_id: int,
    body: AvatarSelectRequest,
    session: AsyncSession = Depends(get_session),
) -> SpeakerResponse:
    """Select an avatar from the library as the active avatar."""
    result = await session.execute(select(SpeakerProfile).where(SpeakerProfile.id == speaker_id))
    speaker = result.scalar_one_or_none()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    # Resolve the source path (body.image_path is like "/media/avatars/speaker_1/001.png")
    # Strip leading /media/ to get relative path
    rel = body.image_path.lstrip("/")
    if rel.startswith("media/"):
        rel = rel[len("media/"):]
    source = os.path.join(settings.media_dir, rel)

    if not os.path.exists(source):
        raise HTTPException(status_code=404, detail="Image not found")

    # Copy to active avatar path
    active_path = os.path.join(settings.media_dir, "avatars", f"speaker_{speaker_id}.png")
    shutil.copy2(source, active_path)
    speaker.avatar_path = active_path
    await session.commit()
    await session.refresh(speaker)
    return SpeakerResponse.model_validate(speaker)
