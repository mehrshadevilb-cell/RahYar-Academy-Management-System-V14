from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class License(Base):
    """
    A SpotPlayer license issued to a student for a purchased product.
    Kept even on failure (status="failed") so nothing is ever lost -
    a failed attempt can be retried later without re-charging the student.
    """

    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False,
    )

    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id"),
        nullable=True,
    )

    spotplayer_license_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    license_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    license_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
    )

    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
