from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class OnlineTimeSlot(Base):
    """A recurring weekly time window configured by the admin for one class."""

    __tablename__ = "online_time_slots"
    __table_args__ = (
        UniqueConstraint("online_course_id", "weekday", "start_time", "end_time", name="uq_online_slot_window"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    online_course_id: Mapped[int] = mapped_column(ForeignKey("online_courses.id"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # Monday=0 ... Sunday=6
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    online_course = relationship("OnlineCourse")

    @property
    def label(self) -> str:
        days = ("دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه")
        return f"{days[self.weekday]} {self.start_time}-{self.end_time}"


__all__ = ["OnlineTimeSlot"]


# Monday=0 is intentionally used internally; the Persian labels above are
# ordered for the user-facing academy week where Saturday is the sixth entry.
# The service converts Telegram/admin day numbers to this canonical value.

def normalize_weekday(value: int) -> int:
    if value < 0 or value > 6:
        raise ValueError("weekday must be between 0 and 6")
    return value


OnlineTimeSlot.normalize_weekday = staticmethod(normalize_weekday)
