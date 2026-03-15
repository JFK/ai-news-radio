"""Settings API for managing application configuration via WebUI."""

from fastapi import APIRouter, Depends
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
