"""Welcome + short rules when a member joins a group where the bot is present."""

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER
from aiogram.types import ChatMemberUpdated

from src.core.config.settings import get_settings

router = Router()
settings = get_settings()


@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_group_member_join(event: ChatMemberUpdated):
    if not settings.GROUP_WELCOME_ENABLED:
        return
    chat = event.chat
    if chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return

    member = event.new_chat_member.user
    if member.is_bot:
        return

    name = (member.full_name or member.username or "دوست").strip()
    # Escape minimal HTML risk in name
    safe_name = (
        name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    text = settings.default_group_welcome_text().format(name=safe_name)
    try:
        await event.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        # Group may restrict the bot from sending messages.
        pass
