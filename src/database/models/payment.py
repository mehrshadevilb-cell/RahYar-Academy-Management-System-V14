from datetime import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    STUDENT = "student"


class User(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )

    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.STUDENT,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    student_profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
    )

    telegram_account = relationship(
        "TelegramAccount",
        back_populates="user",
        uselist=False,
    )

    enrollments = relationship(
        "Enrollment",
        back_populates="user",
    )
