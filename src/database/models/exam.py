from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Exam(Base):
    """Formal exam for an online course (stricter than practice quizzes)."""

    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    online_course_id: Mapped[int] = mapped_column(
        ForeignKey("online_courses.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    pass_score_percent: Mapped[int] = mapped_column(Integer, default=70)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    questions = relationship(
        "ExamQuestion", back_populates="exam", cascade="all, delete-orphan"
    )
    attempts = relationship("ExamAttempt", back_populates="exam")


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    exam = relationship("Exam", back_populates="questions")
    options = relationship(
        "ExamOption", back_populates="question", cascade="all, delete-orphan"
    )


class ExamOption(Base):
    __tablename__ = "exam_options"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("exam_questions.id"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    question = relationship("ExamQuestion", back_populates="options")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    score_percent: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    exam = relationship("Exam", back_populates="attempts")
    answers = relationship(
        "ExamAnswer", back_populates="attempt", cascade="all, delete-orphan"
    )


class ExamAnswer(Base):
    __tablename__ = "exam_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_exam_attempt_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("exam_attempts.id"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("exam_questions.id"), nullable=False, index=True
    )
    selected_option_id: Mapped[int] = mapped_column(
        ForeignKey("exam_options.id"), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    attempt = relationship("ExamAttempt", back_populates="answers")
