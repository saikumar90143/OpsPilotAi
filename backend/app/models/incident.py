"""Incident persistence model."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
