from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class OnlineCourse(Base):
    """
    A live/private online class type (e.g. Arrangement, Mixing, Piano,
    Theory, Harmony, Ear Training) - distinct from the digital SpotPlayer
    products in `courses`. Priced separately for monthly vs term students.
    """

    __tablename__ = "online_courses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(150), nullable=False)

    teacher: Mapped[str | None] = mapped_column(String(100), nullable=True)

    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)

    monthly_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    term_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    monthly_sessions: Mapped[int] = mapped_column(Integer, default=4)

    term_sessions: Mapped[int] = mapped_column(Integer, default=12)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enrollments = relationship("OnlineEnrollment", back_populates="online_course")
