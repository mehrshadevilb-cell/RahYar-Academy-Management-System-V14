"""Group /ask — short educational answers without exposing private student data."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from src.core.config.settings import get_settings
from src.services.chat_assistant_service import ChatAssistantError, ChatAssistantService
from src.services.telegram_answer_ui import format_assistant_answer

router = Router()
settings = get_settings()
_assistant = ChatAssistantService()

_rate: dict[int, deque[float]] = defaultdict(deque)
_WINDOW = 3600
_MAX_GROUP_ANSWER_CHARS = 900


def _group_rate_ok(user_id: int) -> bool:
    limit = max(1, int(settings.GROUP_ASK_MAX_PER_HOUR or 8))
    now = time.time()
    window = _rate[user_id]
    while window and now - window[0] > _WINDOW:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


def _extract_question(message: Message) -> str:
    text = (message.text or "").strip()
    # /ask question...  or  /ask@BotName question
    parts = text.split(maxsplit=1)
    if len(parts) >= 2:
        return parts[1].strip()
    if message.reply_to_message and (message.reply_to_message.text or message.reply_to_message.caption):
        return (message.reply_to_message.text or message.reply_to_message.caption or "").strip()
    return ""


@router.message(Command("ask"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def group_ask(message: Message, db):
    if not settings.GROUP_ASK_ENABLED or not settings.CHAT_ASSISTANT_ENABLED:
        await message.reply("دستیار گروهی فعلاً غیرفعال است.")
        return

    user = message.from_user
    if not user:
        return

    if not _group_rate_ok(user.id):
        await message.reply("⏳ محدودیت /ask در این ساعت پر شده. کمی بعد دوباره تلاش کن یا در چت خصوصی از دستیار استفاده کن.")
        return

    question = _extract_question(message)
    if not question:
        await message.reply(
            "استفاده:\n"
            "• <code>/ask چطور وکال را de-ess کنم؟</code>\n"
            "• یا روی یک پیام ریپلای کن و فقط <code>/ask</code> بزن",
            parse_mode="HTML",
        )
        return

    await message.bot.send_chat_action(message.chat.id, "typing")
    try:
        reply = _assistant.answer(
            db=db,
            telegram_id=str(user.id),
            user_message=question[:800],
        )
    except ChatAssistantError as exc:
        code = str(exc)
        if "تعداد پیام" in code:
            await message.reply("⏳ محدودیت موقت دستیار. کمی بعد دوباره تلاش کن.")
            return
        await message.reply("فعلاً نتوانستم جواب بدهم. از چت خصوصی ربات یا پشتیبانی استفاده کن.")
        return

    short = (reply or "").strip()
    if len(short) > _MAX_GROUP_ANSWER_CHARS:
        short = short[: _MAX_GROUP_ANSWER_CHARS - 1].rsplit(" ", 1)[0] + "…"

    body = format_assistant_answer(short)
    # Keep group noise low — no feedback keyboard in groups.
    await message.reply(body, parse_mode="HTML", disable_web_page_preview=True)
