import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class ReservationStatus(str, enum.Enum):
    WAITING_PAYMENT = "waiting_payment"
    PAYMENT_SUBMITTED = "payment_submitted"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("online_enrollments.id"), nullable=False
    )

    requested_date: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_time: Mapped[str] = mapped_column(String(10), nullable=False)

    # Production Postgres has a native enum type `reservationstatus` whose
    # labels are the Python *member names* (CONFIRMED, PENDING, ...), not the
    # lowercase .value strings. values_callable must send names or queries
    # raise InvalidTextRepresentation.
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(
            ReservationStatus,
            name="reservationstatus",
            values_callable=lambda enum_cls: [item.name for item in enum_cls],
            native_enum=True,
        ),
        default=ReservationStatus.WAITING_PAYMENT,
    )

    payment_proof: Mapped[str | None] = mapped_column(String(500), nullable=True)

    admin_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    reminder_1d_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_due_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enrollment = relationship("OnlineEnrollment", back_populates="reservations")
