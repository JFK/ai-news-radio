import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class EpisodeStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PUBLISHED = "published"


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[EpisodeStatus] = mapped_column(
        Enum(EpisodeStatus, values_callable=lambda e: [x.value for x in e]),
        default=EpisodeStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    news_items: Mapped[list["NewsItem"]] = relationship(back_populates="episode", cascade="all, delete-orphan")
    pipeline_steps: Mapped[list["PipelineStep"]] = relationship(back_populates="episode", cascade="all, delete-orphan")
    api_usages: Mapped[list["ApiUsage"]] = relationship(back_populates="episode", cascade="all, delete-orphan")


from app.models.api_usage import ApiUsage  # noqa: E402
from app.models.news_item import NewsItem  # noqa: E402
from app.models.pipeline_step import PipelineStep  # noqa: E402
