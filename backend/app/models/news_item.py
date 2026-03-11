from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import Base


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episodes.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(String(2000))
    source_name: Mapped[str] = mapped_column(String(200))

    # Fact check
    fact_check_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fact_check_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fact_check_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Analysis
    analysis_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Grouping (similar news consolidation)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    is_group_primary: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Script
    script_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    episode: Mapped["Episode"] = relationship(back_populates="news_items")


from app.models.episode import Episode  # noqa: E402, F811
