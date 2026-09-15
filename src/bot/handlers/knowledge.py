"""Passive group knowledge capture plus AI support for group questions."""
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from src.core.config.settings import get_settings
from src.services.chat_assistant_service import ChatAssistantError, ChatAssistantService
from src.services.knowledge_service import KnowledgeService

router = Router()
settings = get_settings()
knowledge_service = KnowledgeService()
chat_service = ChatAssistantService()


def _looks_like_question(text: str) -> bool:
    lowered = text.lower()
    return "?" in text or "؟" in text or any(token in lowered for token in ("چطور", "چجوری", "چگونه", "چیه", "چیست", "فرق", "کدوم", "چرا", "how ", "what ", "why "))


def _bot_is_target(message: Message) -> bool:
    if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.is_bot:
        return True
    username = (settings.BOT_USERNAME or "").lstrip("@").lower()
    return bool(username and f"@{username}" in (message.text or "").lower())


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.text)
async def capture_and_support_group_message(message: Message, db):
    if not settings.KNOWLEDGE_ENABLED:
        return
    allowed = settings.knowledge_group_ids
    if allowed and message.chat.id not in allowed:
        return
    text = (message.text or message.caption or "").strip()
    if len(text) < 5:
        return
    knowledge_service.ingest_group_message(db, message.chat.id, message.message_id, text)
    if not (_looks_like_question(text) or _bot_is_target(message)):
        return
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
        reply = chat_service.answer(db=db, telegram_id=str(message.from_user.id), user_message=text[:1000])
        await message.reply(reply)
    except ChatAssistantError as exc:
        if str(exc).startswith("تعداد پیام"):
            await message.reply(str(exc))
