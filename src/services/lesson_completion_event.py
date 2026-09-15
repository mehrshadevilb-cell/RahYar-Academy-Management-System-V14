"""Helpers for dispatching lesson completion notifications.

Kept separate from attendance writes so Telegram/network failures never break
attendance recording.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.services.lesson_completion_notification_service import (
    LessonCompletionNotificationService,
)


async def notify_student_lesson_completed(
    *,
    bot_sender,
    student_chat_id: int | None,
    student_name: str,
    session_date: str,
    teacher_name: str | None = None,
    remaining_sessions: int | None = None,
) -> bool:
    if not student_chat_id:
        return False

    service = LessonCompletionNotificationService(sender=bot_sender)

    async def _send():
        return await service.notify_completed(
            chat_id=student_chat_id,
            student_name=student_name,
            session_date=session_date,
            teacher_name=teacher_name,
            remaining_sessions=remaining_sessions,
        )

    try:
        await _send()
        return True
    except Exception:
        # Notification failure must never fail attendance completion.
        return False


def schedule_lesson_completion_notification(**kwargs: Any) -> None:
    """Fire-and-forget entry point for sync attendance flows."""
    try:
        asyncio.create_task(notify_student_lesson_completed(**kwargs))
    except RuntimeError:
        # No active event loop. Caller can retry from worker/queue.
        return
