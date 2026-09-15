"""Notifications after completed in-person lessons."""

from __future__ import annotations

from datetime import date
from typing import Any, Awaitable, Callable


class LessonCompletionNotificationService:
    """Builds and sends a completion notification without blocking attendance flow."""

    def __init__(self, sender: Callable[..., Awaitable[Any]] | None = None):
        self.sender = sender

    def build_message(self, student_name: str, session_date: date | str, teacher_name: str | None = None, remaining_sessions: int | None = None) -> str:
        lines = [
            "🎵 جلسه حضوری شما انجام شد",
            "",
            f"👤 هنرجو: {student_name}",
            f"📅 تاریخ جلسه: {session_date}",
        ]
        if teacher_name:
            lines.append(f"🎓 مدرس: {teacher_name}")
        if remaining_sessions is not None:
            lines.append(f"📌 جلسات باقی‌مانده: {remaining_sessions}")
        lines.append("\nموفق باشید 🌱")
        return "\n".join(lines)

    async def notify_completed(self, chat_id: int, **data: Any) -> bool:
        if not self.sender:
            return False
        await self.sender(chat_id=chat_id, text=self.build_message(**data))
        return True
