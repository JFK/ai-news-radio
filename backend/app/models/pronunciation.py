from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Pronunciation(Base):
    __tablename__ = "pronunciations"

    id: Mapped[int] = mapped_column(primary_key=True)
    surface: Mapped[str] = mapped_column(String(200), unique=True)
    reading: Mapped[str] = mapped_column(String(200))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
