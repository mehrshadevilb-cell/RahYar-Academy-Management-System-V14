from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class ClassSlot(Base):
    """Owner-published available class time. Students pick from this list."""

    __tablename__ = "class_slots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    online_course_id: Mapped[int] = mapped_column(
        ForeignKey("online_courses.id"), nullable=False, index=True
    )

    # Jalali date string, same convention as reservations (e.g. 1404-07-20)
    slot_date: Mapped[str] = mapped_column(String(20), nullable=False)

    slot_time: Mapped[str] = mapped_column(String(10), nullable=False)

    capacity: Mapped[int] = mapped_column(Integer, default=1)

    booked_count: Mapped[int] = mapped_column(Integer, default=0)

    is_open: Mapped[bool] = mapped_column(Boolean, default=True)

    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    online_course = relationship("OnlineCourse", backref="class_slots")

    @property
    def is_available(self) -> bool:
        return self.is_open and self.booked_count < self.capacity
