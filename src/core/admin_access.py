from __future__ import annotations

from typing import Any

from src.core.config.settings import get_settings


def is_admin_user(user_id: int | Any, username: str | None = None) -> bool:
    """Return True for the primary owner or a configured Telegram admin username.

    Accepts either a numeric Telegram user id plus optional username, or an
    aiogram/Telegram user object for safe use directly inside handlers.
    """
    settings = get_settings()
    if not isinstance(user_id, int):
        user = user_id
        username = username if username is not None else getattr(user, "username", None)
        user_id = int(getattr(user, "id", 0) or 0)

    if settings.OWNER_ID and user_id == settings.OWNER_ID:
        return True

    normalized = (username or "").strip().lstrip("@").casefold()
    if not normalized:
        return False

    return normalized in settings.admin_usernames
