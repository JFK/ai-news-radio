"""Pydantic schemas for API request/response models."""

from datetime import datetime

from pydantic import BaseModel, model_validator

# --- Request schemas ---


class EpisodeCreate(BaseModel):
    """Request body for creating an episode."""

    title: str


class ArticleInput(BaseModel):
    """A single article for direct episode creation."""

    title: str
    summary: str | None = None
    source_url: str
    source_name: str


class EpisodeFromArticles(BaseModel):
    """Request body for creating an episode from pre-supplied articles."""

    title: str
    articles: list[ArticleInput]


class RunStepRequest(BaseModel):
    """Optional request body for running a step."""

    queries: list[str] | None = None  # Override collection queries


class RejectRequest(BaseModel):
    """Request body for rejecting a step."""

    reason: str


class ScriptEditRequest(BaseModel):
    """Request body for editing a script."""

    script_text: str


class EpisodeScriptEditRequest(BaseModel):
    """Request body for editing the full episode script."""

    episode_script: str


class PronunciationCreate(BaseModel):
    """Request body for creating a pronunciation entry."""

    surface: str
    reading: str
    priority: int = 0


# --- Response schemas ---


class StepResponse(BaseModel):
    """Response for a single pipeline step."""

    id: int
    episode_id: int
    step_name: str
    status: str
    input_data: dict | None = None
    output_data: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EpisodeResponse(BaseModel):
    """Response for a single episode."""

    id: int
    title: str
    status: str
    created_at: datetime
    published_at: datetime | None = None
    audio_path: str | None = None
    video_path: str | None = None
    pipeline_steps: list[StepResponse] = []

    model_config = {"from_attributes": True}


class EpisodeListResponse(BaseModel):
    """Response for episode listing."""

    episodes: list[EpisodeResponse]
    total: int


_BODY_TRUNCATE_CHARS = 2000


class NewsItemResponse(BaseModel):
    """Response for a single news item."""

    id: int
    episode_id: int
    title: str
    summary: str | None = None
    body: str | None = None
    body_length: int | None = None
    source_url: str
    source_name: str
    fact_check_status: str | None = None
    fact_check_score: int | None = None
    fact_check_details: str | None = None
    reference_urls: list[str] | None = None
    analysis_data: dict | None = None
    script_text: str | None = None
    group_id: int | None = None
    is_group_primary: bool | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def truncate_body(self) -> "NewsItemResponse":
        """Truncate body for API response and expose original length."""
        if self.body is not None:
            self.body_length = len(self.body)
            if len(self.body) > _BODY_TRUNCATE_CHARS:
                self.body = self.body[:_BODY_TRUNCATE_CHARS] + "…"
        return self


class PronunciationResponse(BaseModel):
    """Response for a pronunciation entry."""

    id: int
    surface: str
    reading: str
    priority: int
    created_at: datetime

    model_config = {"from_attributes": True}
