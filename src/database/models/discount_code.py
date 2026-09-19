from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base
from src.core.utils.time import utcnow


class DiscountType(str, enum.Enum):
    """
    PERCENTAGE -> value is 1-100, discount = price * value / 100
    FIXED      -> value is a flat Toman amount subtracted from price
    """

    PERCENTAGE = "percentage"
    FIXED = "fixed"


class DiscountCode(Base):
    """
    A promotional code the owner creates from the admin panel and a
    student redeems during the course purchase flow (see payment.py).

    Usage accounting: `used_count` is incremented the moment a student's
    code is accepted and a pending payment is created with it (a
    "reservation"), and decremented again if that payment is later
    rejected. This keeps `max_uses` reflecting real approved-or-pending
    redemptions rather than being wasted by abandoned/rejected attempts,
    while still preventing a code from being oversold while payments are
    awaiting review. Codes are never deleted (only deactivated), matching
    the project's history-preserving convention for configuration data.
    """

    __tablename__ = "discount_codes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType),
        default=DiscountType.PERCENTAGE,
    )

    value: Mapped[int] = mapped_column(Integer, nullable=False)

    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # None = unlimited number of uses

    used_count: Mapped[int] = mapped_column(Integer, default=0)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # None = never expires

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
