"""SpeakerProfile model for managing speaker/character settings."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50), unique=True)
    voice_name: Mapped[str] = mapped_column(String(50), server_default="Kore")
    voice_instructions: Mapped[str] = mapped_column(Text, server_default="")
    avatar_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_position: Mapped[str] = mapped_column(String(10), server_default="right")
    description: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
