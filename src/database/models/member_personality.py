"""Aggregated interaction style learned from group activity.

Privacy: raw message bodies are NOT stored. Only counters, interest tags,
and a short rolling Persian summary for educational personalization.
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class MemberPersonalityProfile(Base):
    __tablename__ = "member_personality_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    telegram_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    help_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 0..1 rolling scores derived from heuristics
    curiosity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    helpfulness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    politeness_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Comma-separated interest tags e.g. mix,daw,theory
    interest_tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Short human-readable Persian summary for teachers / assistant context
    summary_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Last few signal snippets for LLM refresh only (capped, not full history)
    recent_signals: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_summary_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
