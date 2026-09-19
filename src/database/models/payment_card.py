from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base
from src.core.utils.time import utcnow


class PaymentCard(Base):
    """
    A card-to-card payment destination.

    Kept as data (not hardcoded) so the owner can add/replace/disable
    cards from the admin panel without touching code.
    """

    __tablename__ = "payment_cards"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    card_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    card_holder: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
    )
