from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class ProductDeliveryType(str, enum.Enum):
    """
    How access is delivered to the student after payment approval.
    SPOTPLAYER -> RahYar / Theory (digital courses via SpotPlayer license)
    TELEGRAM   -> ArtistYar (Telegram channel invite links)
    """

    SPOTPLAYER = "spotplayer"
    TELEGRAM = "telegram"


class Course(Base):

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    thumbnail: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    price: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    delivery_type: Mapped[ProductDeliveryType] = mapped_column(
        Enum(ProductDeliveryType),
        default=ProductDeliveryType.SPOTPLAYER,
    )

    support_group_link: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    support_username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    enrollments = relationship(
        "Enrollment",
        back_populates="course",
    )

    spotplayer_courses = relationship(
        "SpotPlayerCourse",
        back_populates="product",
    )

    telegram_channels = relationship(
        "TelegramChannel",
        back_populates="product",
    )
