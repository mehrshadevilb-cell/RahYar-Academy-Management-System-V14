import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Reservation(Base):
    """A student's requested class session, subject to owner approval."""

    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("online_enrollments.id"), nullable=False
    )

    # Optional link to an owner-published ClassSlot.
    class_slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("class_slots.id"), nullable=True, index=True
    )

    # Stored as free text: the academy uses the Jalali calendar, and
    # this is exactly what the student typed (e.g. "1404-07-20"),
    # not a Gregorian date - a real Date column would corrupt it.
    requested_date: Mapped[str] = mapped_column(String(20), nullable=False)

    requested_time: Mapped[str] = mapped_column(String(10), nullable=False)

    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.PENDING
    )

    admin_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Idempotent reminder flags (same pattern as installments).
    reminder_1d_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_due_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enrollment = relationship("OnlineEnrollment", back_populates="reservations")

    class_slot = relationship("ClassSlot")
