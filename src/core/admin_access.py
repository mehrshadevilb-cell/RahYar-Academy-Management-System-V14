"""Single source of truth for academy admin authorization.

RULE (mandatory for every new admin feature):
    Always gate with ``is_admin_user(...)`` (or ``require_admin``).
    Never check OWNER_ID alone. Never invent a parallel admin list.

Who counts as admin:
    1. OWNER_ID
    2. Any numeric id in ADMIN_IDS (comma-separated env)
    3. Any username in ADMIN_USERNAMES (comma-separated env, case-insensitive)

All of the above receive the **same full admin capabilities** in Telegram
(panel, payments, support, AI agent UI, group /admin_quick, etc.).
"""
from __future__ import annotations

from typing import Any

from src.core.config.settings import get_settings


def is_admin_user(user_id: int | Any, username: str | None = None) -> bool:
    """Return True for the owner or any configured admin (id or username).

    Accepts either a numeric Telegram user id plus optional username, or an
    aiogram/Telegram user object for safe use directly inside handlers.
    """
    settings = get_settings()
    if not isinstance(user_id, int):
        user = user_id
        username = username if username is not None else getattr(user, "username", None)
        user_id = int(getattr(user, "id", 0) or 0)

    if user_id <= 0:
        return False

    if settings.OWNER_ID and user_id == settings.OWNER_ID:
        return True

    if user_id in settings.admin_ids:
        return True

    normalized = (username or "").strip().lstrip("@").casefold()
    if normalized and normalized in settings.admin_usernames:
        return True

    return False


def require_admin(user: Any) -> bool:
    """Thin alias used by new handlers so the gate stays obvious and consistent."""
    return is_admin_user(user)


def all_admin_telegram_ids() -> set[int]:
    """Every configured admin chat id (for notifications that must reach all admins)."""
    settings = get_settings()
    ids: set[int] = set(settings.admin_ids)
    if settings.OWNER_ID:
        ids.add(int(settings.OWNER_ID))
    return {i for i in ids if i}
