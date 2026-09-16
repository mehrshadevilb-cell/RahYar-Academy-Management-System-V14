"""Observe group messages to learn member interaction style (no full chat archive)."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from src.core.admin_access import is_admin_user
from src.core.config.settings import get_settings
from src.services.member_personality_service import MemberPersonalityService

router = Router()
logger = logging.getLogger(__name__)
_service = MemberPersonalityService()
settings = get_settings()


def _learning_groups() -> set[int]:
    raw = getattr(settings, "GROUP_LEARNING_CHAT_IDS", "") or ""
    ids: set[int] = set()
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            continue
    # Empty set means: all groups where the bot can see messages.
    return ids


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.text)
async def observe_group_text(message: Message, db):
    if not getattr(settings, "GROUP_LEARNING_ENABLED", True):
        return
    if not message.from_user or message.from_user.is_bot:
        return
    # Ignore commands — other handlers own them.
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    allowed = _learning_groups()
    if allowed and message.chat.id not in allowed:
        return

    try:
        _service.observe_message(
            db,
            telegram_id=str(message.from_user.id),
            text=text,
            display_name=message.from_user.full_name,
        )
    except Exception:
        logger.exception("member personality observe failed")


@router.message(Command("member_profile"))
async def admin_member_profile(message: Message, db):
    """Admin-only: show learned profile for a user (reply or /member_profile <telegram_id>)."""
    if not message.from_user or not is_admin_user(message.from_user):
        if message.chat.type == ChatType.PRIVATE:
            await message.answer("⛔️ فقط ادمین.")
        return

    target_id: str | None = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = str(message.reply_to_message.from_user.id)
    else:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) == 2 and parts[1].strip().lstrip("-").isdigit():
            target_id = parts[1].strip()

    if not target_id:
        await message.answer(
            "استفاده:\n"
            "• ریپلای روی پیام فرد + /member_profile\n"
            "• /member_profile 123456789"
        )
        return

    profile = _service.get_by_telegram_id(db, target_id)
    if not profile:
        await message.answer("هنوز پروفایل تعاملی برای این کاربر ساخته نشده (پیام گروهی کافی دیده نشده).")
        return
    await message.answer(_service.format_admin_view(profile))
