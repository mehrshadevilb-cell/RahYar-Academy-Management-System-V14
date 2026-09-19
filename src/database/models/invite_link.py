from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base
from src.core.utils.time import utcnow


class TelegramInviteLink(Base):
    """
    A one-time (member_limit=1) invite link generated for a student to
    join one of a product's Telegram channels (ArtistYar delivery).
    Kept permanently as a record of what access was granted and when.
    """

    __tablename__ = "telegram_invite_links"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    channel_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_channels.id"),
        nullable=False,
    )

    invite_link: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    member_limit: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )
