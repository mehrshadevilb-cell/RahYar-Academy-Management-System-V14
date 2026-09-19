from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.core.utils.time import utcnow


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    RETURNED = "returned"


class Assignment(Base):
    """Homework / practice task attached to an online course type."""

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    online_course_id: Mapped[int] = mapped_column(
        ForeignKey("online_courses.id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    online_course = relationship("OnlineCourse", backref="assignments")

    submissions = relationship("AssignmentSubmission", back_populates="assignment")


class AssignmentSubmission(Base):
    """One student submission per assignment."""

    __tablename__ = "assignment_submissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id"), nullable=False, index=True
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus), default=SubmissionStatus.PENDING, index=True
    )

    admin_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    assignment = relationship("Assignment", back_populates="submissions")
