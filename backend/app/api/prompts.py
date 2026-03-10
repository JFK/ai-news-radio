"""API endpoints for managing prompt templates."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.pipeline.analyzer  # noqa: F401

# Import pipeline modules to register their default prompts
import app.pipeline.factchecker  # noqa: F401
import app.pipeline.scriptwriter  # noqa: F401
import app.pipeline.video  # noqa: F401
from app.database import get_session
from app.models.prompt_template import PromptTemplate
from app.services.prompt_loader import get_all_defaults

router = APIRouter()

# Display names for prompt keys
PROMPT_NAMES: dict[str, str] = {
    "factcheck": "ファクトチェック",
    "analysis": "クリティカル分析",
    "script_item": "台本生成（個別記事）",
    "script_episode": "台本生成（エピソード構成）",
    "youtube_metadata": "YouTube メタデータ",
}


class PromptTemplateResponse(BaseModel):
    id: int
    key: str
    name: str
    content: str
    version: int
    is_active: bool
    created_at: str
    updated_at: str


class PromptSummaryResponse(BaseModel):
    key: str
    name: str
    active_version: int | None
    has_custom: bool
    content_preview: str


class PromptUpdateRequest(BaseModel):
    content: str


class PromptHistoryResponse(BaseModel):
    key: str
    name: str
    default_content: str
    active_version: int | None
    versions: list[PromptTemplateResponse]


def _to_response(t: PromptTemplate) -> PromptTemplateResponse:
    return PromptTemplateResponse(
        id=t.id,
        key=t.key,
        name=t.name,
        content=t.content,
        version=t.version,
        is_active=t.is_active,
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat(),
    )


@router.get("/prompts", response_model=list[PromptSummaryResponse])
async def list_prompts(session: AsyncSession = Depends(get_session)):
    """List all prompt templates (one entry per key) with active version info."""
    defaults = get_all_defaults()

    # Get all active templates
    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.is_active == True).order_by(  # noqa: E712
            PromptTemplate.key
        )
    )
    active_templates = {t.key: t for t in result.scalars().all()}

    summaries = []
    for key in PROMPT_NAMES:
        name = PROMPT_NAMES[key]
        template = active_templates.get(key)
        content = template.content if template else defaults.get(key, "")
        summaries.append(
            PromptSummaryResponse(
                key=key,
                name=name,
                active_version=template.version if template else None,
                has_custom=template is not None,
                content_preview=content[:100] + "..." if len(content) > 100 else content,
            )
        )

    return summaries


@router.get("/prompts/{key}", response_model=PromptHistoryResponse)
async def get_prompt(key: str, session: AsyncSession = Depends(get_session)):
    """Get a prompt template with full version history."""
    if key not in PROMPT_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key: {key}")

    defaults = get_all_defaults()

    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.key == key).order_by(PromptTemplate.version.desc())
    )
    versions = [_to_response(t) for t in result.scalars().all()]

    active_version = None
    for v in versions:
        if v.is_active:
            active_version = v.version
            break

    return PromptHistoryResponse(
        key=key,
        name=PROMPT_NAMES[key],
        default_content=defaults.get(key, ""),
        active_version=active_version,
        versions=versions,
    )


@router.put("/prompts/{key}", response_model=PromptTemplateResponse)
async def update_prompt(key: str, body: PromptUpdateRequest, session: AsyncSession = Depends(get_session)):
    """Update a prompt template (creates a new version)."""
    if key not in PROMPT_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key: {key}")

    # Get current max version
    result = await session.execute(
        select(PromptTemplate.version).where(PromptTemplate.key == key).order_by(
            PromptTemplate.version.desc()
        ).limit(1)
    )
    max_version = result.scalar_one_or_none() or 0

    # Deactivate all existing versions for this key
    await session.execute(
        update(PromptTemplate).where(PromptTemplate.key == key).values(is_active=False)
    )

    # Create new version
    new_template = PromptTemplate(
        key=key,
        name=PROMPT_NAMES[key],
        content=body.content,
        version=max_version + 1,
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    session.add(new_template)
    await session.commit()
    await session.refresh(new_template)

    return _to_response(new_template)


@router.post("/prompts/{key}/rollback/{version}", response_model=PromptTemplateResponse)
async def rollback_prompt(key: str, version: int, session: AsyncSession = Depends(get_session)):
    """Rollback to a specific version (makes it active, deactivates others)."""
    if key not in PROMPT_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key: {key}")

    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.key == key, PromptTemplate.version == version)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail=f"Version {version} not found for key: {key}")

    # Deactivate all versions
    await session.execute(
        update(PromptTemplate).where(PromptTemplate.key == key).values(is_active=False)
    )

    # Activate the target version
    target.is_active = True
    target.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(target)

    return _to_response(target)


@router.delete("/prompts/{key}", status_code=204)
async def reset_prompt(key: str, session: AsyncSession = Depends(get_session)):
    """Reset to default by deactivating all custom versions."""
    if key not in PROMPT_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key: {key}")

    await session.execute(
        update(PromptTemplate).where(PromptTemplate.key == key).values(is_active=False)
    )
    await session.commit()
