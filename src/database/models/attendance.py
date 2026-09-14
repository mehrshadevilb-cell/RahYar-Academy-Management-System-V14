import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    CANCELLED = "cancelled"


class Attendance(Base):
    """
    A recorded class session outcome.

    Session consumption rules:
    - PRESENT always consumes one remaining session.
    - ABSENT does not consume a session (no-show without formal cancel).
    - CANCELLED: the first free cancel per enrollment term does NOT consume;
      any further cancel is treated like a charged absence and consumes one session.
    """

    __tablename__ = "attendances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("online_enrollments.id"), nullable=False
    )

    reservation_id: Mapped[int | None] = mapped_column(
        ForeignKey("reservations.id"), nullable=True
    )

    # Same Jalali-text storage as Reservation.requested_date, since this
    # is copied directly from the reservation the attendance is for.
    session_date: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus))

    admin_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enrollment = relationship("OnlineEnrollment", back_populates="attendances")
