"""Organization invitation model."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.membership import ROLE_COLUMN_LENGTH
from app.models.refresh_token import TOKEN_HASH_LENGTH
from app.models.user import EMAIL_MAX_LENGTH


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(ROLE_COLUMN_LENGTH), nullable=False)
    token_hash: Mapped[str] = mapped_column(
        String(TOKEN_HASH_LENGTH), nullable=False, unique=True, index=True
    )
    invited_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
