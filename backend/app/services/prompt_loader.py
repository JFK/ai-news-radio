"""Load prompt templates from DB with fallback to code defaults."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate

logger = logging.getLogger(__name__)

# Registry of default prompts (populated by pipeline steps at import time)
_defaults: dict[str, str] = {}


def register_default(key: str, content: str) -> None:
    """Register a default prompt for a given key."""
    _defaults[key] = content


def get_default(key: str) -> str:
    """Get the default prompt for a given key."""
    return _defaults.get(key, "")


def get_all_defaults() -> dict[str, str]:
    """Get all registered default prompts."""
    return dict(_defaults)


async def get_active_prompt(session: AsyncSession, key: str) -> tuple[str, int | None]:
    """Get the active prompt for a key.

    Returns:
        Tuple of (prompt_content, version_or_None).
        version is None when using the code default.
    """
    result = await session.execute(
        select(PromptTemplate).where(
            PromptTemplate.key == key,
            PromptTemplate.is_active == True,  # noqa: E712
        ).order_by(PromptTemplate.version.desc()).limit(1)
    )
    template = result.scalar_one_or_none()

    if template:
        return template.content, template.version

    default = _defaults.get(key)
    if default:
        return default, None

    logger.warning("No prompt found for key=%s", key)
    return "", None
