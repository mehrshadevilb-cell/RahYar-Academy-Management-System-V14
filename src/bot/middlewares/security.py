"""Cross-cutting security middleware applied to every incoming
Telegram update (messages and callback queries), regardless of which
feature/router eventually would have handled it:

1. Flood control - a simple in-memory sliding-window rate limit per
   Telegram user. Independent of any single feature's own limit (e.g.
   the chat assistant's paid-API quota); this protects the bot and the
   database from a single user hammering the event loop with
   rapid-fire messages/callbacks.
2. Blocked-user gate - a user an admin has deactivated
   (User.is_active == False) can no longer trigger *any* handler,
   including admin-panel entry points reachable via forged callback
   data, the AI chat assistant, or the music generator.

Registration order matters: this MUST be added AFTER DatabaseMiddleware
in bot.py so that data["db"] is already populated when this runs.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.database.repositories.profile_repository import ProfileRepository

FLOOD_WINDOW_SECONDS = 10
FLOOD_MAX_UPDATES = 15

BLOCKED_MESSAGE_FA = (
    "⛔ دسترسی شما به ربات توسط مدیریت محدود شده است.\n"
    "برای پیگیری با پشتیبانی آکادمی تماس بگیرید."
)
FLOOD_MESSAGE_FA = "⏳ لطفاً کمی آرام‌تر پیام ارسال کنید و دوباره تلاش کنید."


class SecurityMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._repository = ProfileRepository()
        # Per-process, per-Telegram-user sliding window. A single bot
        # instance is the deployment model here, so in-memory is
        # sufficient (same reasoning as ChatAssistantService's limiter).
        self._recent_updates: dict[int, deque[float]] = defaultdict(deque)

    def _is_flooding(self, telegram_id: int) -> bool:
        now = time.monotonic()
        window = self._recent_updates[telegram_id]
        while window and now - window[0] > FLOOD_WINDOW_SECONDS:
            window.popleft()
        window.append(now)
        return len(window) > FLOOD_MAX_UPDATES

    async def __call__(self, handler, event: TelegramObject, data: dict):
        telegram_user = getattr(event, "from_user", None)
        if telegram_user is None:
            return await handler(event, data)

        telegram_id = telegram_user.id

        if self._is_flooding(telegram_id):
            # Only warn once per window (the first update past the
            # limit); otherwise the warning itself becomes part of the
            # flood. Every other excess update is dropped silently but
            # a callback query still gets answered so the button in
            # the user's Telegram client doesn't spin forever.
            window = self._recent_updates[telegram_id]
            is_first_excess = len(window) == FLOOD_MAX_UPDATES + 1
            await self._deny(event, FLOOD_MESSAGE_FA if is_first_excess else None)
            return None

        db = data.get("db")
        if db is not None:
            user = self._repository.get_user_by_telegram_id(db, str(telegram_id))
            if user is not None and not user.is_active:
                await self._deny(event, BLOCKED_MESSAGE_FA)
                return None

        return await handler(event, data)

    @staticmethod
    async def _deny(event: TelegramObject, text: str | None) -> None:
        """Answers exactly once regardless of update type, so a
        CallbackQuery never gets .answer() called twice (Telegram
        rejects the second call) and a blocked/flooding user always
        gets clear, immediate feedback instead of silence."""
        try:
            if isinstance(event, CallbackQuery):
                if text:
                    await event.answer(text, show_alert=True)
                else:
                    await event.answer()
            elif isinstance(event, Message) and text:
                await event.answer(text)
        except Exception:
            # A failure to notify must never break the security gate
            # itself - the block/flood decision above already stands.
            pass
