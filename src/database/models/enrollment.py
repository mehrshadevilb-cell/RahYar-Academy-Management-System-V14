from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Enrollment(Base):

    __tablename__ = "enrollments"


    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )


    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )


    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False,
    )


    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


    course = relationship(
        "Course",
        back_populates="enrollments",
    )


    user = relationship(
        "User",
        back_populates="enrollments",
    )


    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "course_id",
            name="unique_user_course_enrollment",
        ),
    )