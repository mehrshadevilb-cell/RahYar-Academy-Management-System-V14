"""Passive knowledge capture from configured Telegram groups."""
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from src.core.config.settings import get_settings
from src.services.knowledge_service import KnowledgeService

router = Router()
settings = get_settings()
service = KnowledgeService()


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.text)
async def capture_group_message(message: Message, db):
    if not settings.KNOWLEDGE_ENABLED:
        return
    allowed = settings.knowledge_group_ids
    if allowed and message.chat.id not in allowed:
        return
    # Keep the knowledge base focused on meaningful educational content.
    text = (message.text or message.caption or "").strip()
    if len(text) < 5:
        return
    service.ingest_group_message(db, message.chat.id, message.message_id, text)
