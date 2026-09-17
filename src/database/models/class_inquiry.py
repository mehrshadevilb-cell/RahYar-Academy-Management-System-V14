from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class ClassInquiryStatus(str, enum.Enum):
    PENDING = "pending"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    ENROLLED = "enrolled"


class ClassInquiry(Base):
    """One shared website/bot request for a live online class."""

    __tablename__ = "class_inquiries"
    __table_args__ = (
        Index("ix_class_inquiries_user_status", "user_id", "status"),
        Index("ix_class_inquiries_course_status", "online_course_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    online_course_id: Mapped[int] = mapped_column(
        ForeignKey("online_courses.id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="website")
    requested_plan: Mapped[str | None] = mapped_column(String(30), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ClassInquiryStatus] = mapped_column(
        Enum(ClassInquiryStatus), nullable=False, default=ClassInquiryStatus.PENDING, index=True
    )
    reviewed_by_telegram_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="class_inquiries")
    online_course = relationship("OnlineCourse", backref="class_inquiries")
