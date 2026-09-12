import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class InstallmentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"


class Installment(Base):
    """
    One payment cycle for a monthly-plan online student. A new one is
    created automatically after every 4 PRESENT sessions of the previous
    cycle. Reminder flags exist so a future scheduler phase can send
    7/3/1-day-before and due-date notifications without re-sending them.
    """

    __tablename__ = "installments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("online_enrollments.id"), nullable=False
    )

    installment_number: Mapped[int] = mapped_column(Integer, nullable=False)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)

    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[InstallmentStatus] = mapped_column(
        Enum(InstallmentStatus), default=InstallmentStatus.PENDING
    )

    reminder_7d_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_3d_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_1d_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_due_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enrollment = relationship("OnlineEnrollment", back_populates="installments")
