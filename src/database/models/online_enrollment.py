import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class PaymentModel(str, enum.Enum):
    """How the student pays for online classes.

    Classes meet once per week:
    - MONTHLY: one payment unlocks 4 sessions (~1 month).
    - TERM: 12 sessions over ~3 months (typically 3 installments of 4).
    """

    MONTHLY = "monthly"
    TERM = "term"


class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


# How many free cancellations a student may use during one enrollment term
# without consuming a paid session. Further cancellations count as absence
# and consume remaining_sessions.
FREE_CANCELS_PER_TERM = 1


class OnlineEnrollment(Base):
    """
    A student's enrollment in one online class. Session counters and
    installment cycles are tracked here; attendance/reservations point
    back to this record rather than directly to the user, so a student
    taking the same course twice (different terms) stays distinguishable.
    """

    __tablename__ = "online_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    online_course_id: Mapped[int] = mapped_column(
        ForeignKey("online_courses.id"), nullable=False
    )

    payment_model: Mapped[PaymentModel] = mapped_column(Enum(PaymentModel))

    remaining_sessions: Mapped[int] = mapped_column(Integer, default=0)

    completed_sessions: Mapped[int] = mapped_column(Integer, default=0)

    current_installment_number: Mapped[int] = mapped_column(Integer, default=0)

    # Free cancellations already used in this enrollment (max FREE_CANCELS_PER_TERM).
    free_cancels_used: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus), default=EnrollmentStatus.ACTIVE
    )

    admin_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    online_course = relationship("OnlineCourse", back_populates="enrollments")

    reservations = relationship("Reservation", back_populates="enrollment")

    attendances = relationship("Attendance", back_populates="enrollment")

    installments = relationship("Installment", back_populates="enrollment")
