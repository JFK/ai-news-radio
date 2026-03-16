"""Settings API for managing application configuration via WebUI."""

import os

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.database import get_session
from app.models.app_setting import AppSetting

router = APIRouter(tags=["settings"])

# Keys that should be masked in GET responses
SENSITIVE_KEYS = {
    "anthropic_api_key",
    "openai_api_key",
    "google_api_key",
    "brave_search_api_key",
    "elevenlabs_api_key",
    "google_drive_client_secret",
}

# Keys managed internally (not editable via settings UI)
INTERNAL_KEYS = {"google_drive_refresh_token", "google_drive_redirect_base"}

# Keys that should NOT be exposed/editable via API (infrastructure settings)
EXCLUDED_KEYS = {"database_url", "redis_url", "media_dir"}


def _mask_value(value: str, prefix_len: int = 4, suffix_len: int = 4) -> str:
    """Mask a sensitive value, keeping prefix and suffix visible."""
    if not value:
        return ""
    if len(value) <= prefix_len + suffix_len + 2:
        # Too short to mask meaningfully
        return "***"
    return f"{value[:prefix_len]}...{value[-suffix_len:]}"


class SettingsUpdate(BaseModel):
    settings: dict[str, str]


@router.get("/settings")
async def get_settings(session: AsyncSession = Depends(get_session)) -> dict:
    """Get all configurable settings with current values."""
    all_settings: dict[str, str] = {}
    masked_keys: list[str] = []
    for key, field_info in Settings.model_fields.items():
        if key in EXCLUDED_KEYS or key in INTERNAL_KEYS or key == "model_config":
            continue
        value = getattr(settings, key)
        if key in SENSITIVE_KEYS:
            str_val = str(value) if value else ""
            all_settings[key] = _mask_value(str_val)
            if str_val:
                masked_keys.append(key)
        else:
            if isinstance(value, bool):
                all_settings[key] = "true" if value else "false"
            else:
                all_settings[key] = str(value) if value is not None else ""
    return {"settings": all_settings, "masked_keys": masked_keys}


@router.put("/settings")
async def update_settings(
    body: SettingsUpdate, session: AsyncSession = Depends(get_session)
) -> dict:
    """Update settings. Values are persisted to DB and applied to in-memory config."""
    updated: list[str] = []
    for key, value in body.settings.items():
        if key in EXCLUDED_KEYS or key in INTERNAL_KEYS:
            continue
        if not hasattr(settings, key):
            continue

        # Upsert to DB
        result = await session.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
        else:
            session.add(AppSetting(key=key, value=value))

        # Update in-memory settings
        field_info = Settings.model_fields.get(key)
        if field_info:
            annotation = field_info.annotation
            if annotation is bool:
                val: object = value.lower() in ("true", "1", "yes")
            elif annotation is int:
                val = int(value) if value else 0
            elif annotation is float:
                val = float(value) if value else 0.0
            else:
                val = value
            object.__setattr__(settings, key, val)

        updated.append(key)

    await session.commit()
    return {"updated": updated}


@router.post("/settings/upload-logo")
async def upload_logo(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Upload a logo image for video/thumbnail overlay."""
    if not file.content_type or not file.content_type.startswith("image/"):
        return {"error": "Only image files are accepted"}

    # Save to media directory
    logo_dir = os.path.join(settings.media_dir, "branding")
    os.makedirs(logo_dir, exist_ok=True)
    logo_path = os.path.join(logo_dir, "logo.png")

    content = await file.read()
    with open(logo_path, "wb") as f:
        f.write(content)

    # Update video_logo_path setting in DB and memory
    result = await session.execute(
        select(AppSetting).where(AppSetting.key == "video_logo_path")
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = logo_path
    else:
        session.add(AppSetting(key="video_logo_path", value=logo_path))
    object.__setattr__(settings, "video_logo_path", logo_path)
    await session.commit()

    return {"path": logo_path}


@router.get("/settings/se-presets")
async def get_se_presets() -> dict:
    """List available sound effect presets per position."""
    from app.services.sound_effects import list_se_presets as _list

    return {"presets": _list()}


@router.post("/settings/se-upload/{position}")
async def upload_se(position: str, file: UploadFile) -> dict:
    """Upload a custom SE WAV file for a given position (intro/transition/outro)."""
    from app.services.sound_effects import save_custom_se

    if position not in ("intro", "transition", "outro"):
        return {"error": "Invalid position. Must be intro, transition, or outro."}
    if not file.filename or not file.filename.lower().endswith(".wav"):
        return {"error": "Only WAV files are accepted."}
    content = await file.read()
    preset_name = save_custom_se(position, file.filename, content)
    return {"preset_name": preset_name}


@router.delete("/settings/se/{preset_name}")
async def delete_se(preset_name: str) -> dict:
    """Delete a custom SE file."""
    from app.services.sound_effects import delete_custom_se

    if delete_custom_se(preset_name):
        return {"deleted": True}
    return {"error": "Cannot delete built-in presets or file not found."}
