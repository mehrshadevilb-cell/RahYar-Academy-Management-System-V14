from __future__ import annotations

from pydantic import BaseModel


class ClassOut(BaseModel):
    """Public online-class fields consumed by the ArtistYar catalogue."""

    id: int
    name: str
    description: str | None = None
    teacher: str | None = None
    duration_minutes: int
    monthly_price: int | None = None
    term_price: int | None = None
    monthly_sessions: int
    term_sessions: int
    is_active: bool = True


def class_out(course) -> ClassOut:
    """Serialize the planning details needed before a student requests a class."""
    return ClassOut(
        id=course.id,
        name=course.name,
        description=getattr(course, "description", None),
        teacher=course.teacher,
        duration_minutes=course.duration_minutes,
        monthly_price=course.monthly_price,
        term_price=course.term_price,
        monthly_sessions=course.monthly_sessions,
        term_sessions=course.term_sessions,
        is_active=bool(course.is_active),
    )
