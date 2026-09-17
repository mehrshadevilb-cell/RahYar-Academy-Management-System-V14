from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class ProjectStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    CLOSED = "closed"


class ApplicationStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    SHORTLISTED = "shortlisted"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class Project(Base):
    __tablename__ = "marketplace_projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    employer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    employer_contact: Mapped[str] = mapped_column(String(180), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    skills: Mapped[str] = mapped_column(Text, nullable=False, default="")
    budget_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline: Mapped[str | None] = mapped_column(String(80), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), nullable=False, default=ProjectStatus.PENDING_REVIEW, index=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    applications = relationship("ProjectApplication", back_populates="project", cascade="all, delete-orphan")


class ProjectApplication(Base):
    __tablename__ = "marketplace_project_applications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("marketplace_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    student_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    cover_letter: Mapped[str] = mapped_column(Text, nullable=False)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus), nullable=False, default=ApplicationStatus.SUBMITTED, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="applications")
