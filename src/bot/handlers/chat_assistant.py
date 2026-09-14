"""Catch-all conversational fallback.

This router MUST be the last one registered in src/bot/bot.py's
setup_handlers(). Every other router claims specific commands, exact
reply-keyboard button texts, or specific FSM states; aiogram stops at
the first router whose filters match. Registering this one last means
it only ever sees free text that nothing else in the bot recognized -
exactly the "user is asking a question in plain language" case this is
for. It never intercepts an active flow (StateFilter(None) requires no
FSM state to be in progress).
"""

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from src.services.chat_assistant_service import ChatAssistantError, ChatAssistantService
from src.services.profile_service import ProfileService

router = Router()

chat_assistant_service = ChatAssistantService()
profile_service = ProfileService()


@router.message(StateFilter(None), F.text)
async def chat_fallback(message: Message, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ لطفاً ابتدا دستور /start را بزنید.")
        return

    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        reply = chat_assistant_service.answer(
            db=db,
            telegram_id=str(message.from_user.id),
            user_message=message.text,
        )
    except ChatAssistantError as exc:
        code = str(exc)
        if code == "empty_message":
            return
        if "تعداد پیام" in code:
            await message.answer(code)
            return
        # Disabled / misconfigured / provider failure - never expose the
        # internal reason to the student; guide them to a working path
        # instead of leaving the message unanswered.
        await message.answer(
            "🤖 دستیار گفتگو در حال حاضر در دسترس نیست.\n"
            "برای راهنمایی از منوی اصلی استفاده کنید یا از «🆘 پشتیبانی» پیام بگذارید."
        )
        return

    await message.answer(reply)
