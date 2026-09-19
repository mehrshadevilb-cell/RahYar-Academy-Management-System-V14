from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base
from src.core.utils.time import utcnow


class SupportStatus(str, enum.Enum):
    OPEN = "open"
    ANSWERED = "answered"
    CLOSED = "closed"


class SupportRequest(Base):
    """Student support ticket submitted via Telegram.

    Students open tickets; the owner replies or closes them from the admin panel.
    Message and reply text are capped to keep Telegram UX readable.
    """

    __tablename__ = "support_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    telegram_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[SupportStatus] = mapped_column(
        Enum(SupportStatus), default=SupportStatus.OPEN, index=True
    )

    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
