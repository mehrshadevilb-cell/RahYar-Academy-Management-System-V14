import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class ClassSlotStatus(str, enum.Enum):
    OPEN = "open"
    BOOKED = "booked"
    CLOSED = "closed"


class ClassSlot(Base):
    """Owner-published available class times that students can request."""

    __tablename__ = "class_slots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    online_course_id: Mapped[int] = mapped_column(
        ForeignKey("online_courses.id"), nullable=False, index=True
    )

    # Jalali date string e.g. "1404-07-20" — same convention as Reservation.
    slot_date: Mapped[str] = mapped_column(String(20), nullable=False)

    slot_time: Mapped[str] = mapped_column(String(10), nullable=False)

    capacity: Mapped[int] = mapped_column(Integer, default=1)

    booked_count: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[ClassSlotStatus] = mapped_column(
        Enum(ClassSlotStatus), default=ClassSlotStatus.OPEN
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    online_course = relationship("OnlineCourse", back_populates="class_slots")
