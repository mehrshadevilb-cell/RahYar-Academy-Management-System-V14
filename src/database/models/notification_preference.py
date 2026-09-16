"""Per-user notification mute preferences."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class NotificationPreference(Base):
    """Defaults are all enabled (True). User may disable categories."""

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    installment_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    class_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    broadcast_messages: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
