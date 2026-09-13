from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
    )

    amount: Mapped[int] = mapped_column(
        BigInteger,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
    )

    receipt_file_id: Mapped[str | None] = mapped_column(
        String(255),
    )

    admin_notes: Mapped[str | None] = mapped_column(
        String(500),
    )

    approved_by_id: Mapped[int | None] = mapped_column(
        BigInteger,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    transaction_id: Mapped[str | None] = mapped_column(
        String(100),
    )

    discount_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("discount_codes.id"),
        nullable=True,
    )

    discount_amount: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )