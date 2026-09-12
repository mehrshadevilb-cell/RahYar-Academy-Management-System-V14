from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class TelegramChannel(Base):
    """
    A Telegram channel that ArtistYar-type products deliver access to
    (e.g. Record / Edit / Files). One-time invite links are generated
    per student for each enabled channel of the purchased product.
    """

    __tablename__ = "telegram_channels"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    chat_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    product = relationship(
        "Course",
        back_populates="telegram_channels",
    )
