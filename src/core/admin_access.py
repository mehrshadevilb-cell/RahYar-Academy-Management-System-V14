from __future__ import annotations

from src.core.config.settings import get_settings


def is_admin_user(user_id: int, username: str | None = None) -> bool:
    """Return True for the primary owner or configured Telegram admin usernames."""
    settings = get_settings()
    if settings.OWNER_ID and user_id == settings.OWNER_ID:
        return True

    normalized = (username or "").strip().lstrip("@").casefold()
    if not normalized:
        return False

    return normalized in settings.admin_usernames
