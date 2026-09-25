"""Chat assistant: explicit entry point plus a minimal free-text fallback."""

import asyncio

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, KeyboardButton, MessageEntityType

from src.services.chat_assistant_service import ChatAssistantError, ChatAssistantService
from src.services.profile_service import ProfileService
from src.services.telegram_answer_ui import format_assistant_answer

router = Router()
chat_assistant_service = ChatAssistantService()
profile_service = ProfileService()

MENU_BUTTON_TEXT = "🤖 دستیار هوشمند"
DISABLED_MESSAGE_FA = "🤖 <b>راه‌یار</b>\n\nدستیار فعلاً در دسترس نیست.\nاز «🆘 پشتیبانی» کمک بگیر."
ASSISTANT_HINTS = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎚️ راهنمای DAW")],
        [KeyboardButton(text="🎛️ راهنمای Plugin"), KeyboardButton(text="🎼 تئوری موسیقی")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder="سؤالت رو بنویس…",
)
_recent_questions: dict[int, tuple[str, str]] = {}
_MAX_RECENT_QUESTIONS = 200
# Show the visible "analyzing" line only when the model is truly slow.
_SLOW_RESPONSE_SECONDS = 1.5
_MAX_ANSWER_CHUNK = 3900
_BOT_USERNAME: str | None = None
_CASUAL_MESSAGES = {
    "سلام", "درود", "خوبی", "مرسی", "ممنون", "خداحافظ", "bye", "hi", "hello", "thanks",
}
_QUESTION_STARTERS = (
    "چطور", "چگونه", "چرا", "آیا", "چی", "چه", "کجا", "کی", "میشه", "میتونی", "می‌توانی",
    "how", "why", "what", "where", "when", "can you", "could you",
)
_QUESTION_CONTEXT = (
    "سوال", "راهنما", "قیمت", "خرید", "پرداخت", "دسترسی", "دوره", "خطا", "ارور", "مشکل",
    "میکس", "مستر", "ضبط", "plugin", "daw", "مقایسه", "پیشنهاد", "تنظیم",
)
_FOLLOW_UP_MARKERS = (
    "و بعد", "بعدش", "ادامه بده", "بیشتر بگو", "ادامه", "بعدی", "همینطور",
    "continue", "more", "and then",
)


def assistant_feedback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 مفید بود", callback_data="assistant_feedback:up"),
                InlineKeyboardButton(text="👎 نیاز به اصلاح", callback_data="assistant_feedback:down"),
            ],
            [InlineKeyboardButton(text="🔄 پاسخ بهتر", callback_data="assistant_retry")],
        ]
    )


def should_show_feedback(question: str) -> bool:
    """Show feedback only for a complete information/help question.

    Partial follow-ups ("ادامه بده", "بیشتر بگو") and casual turns must not
    get feedback buttons — those are mid-conversation, not finished answers.
    """
    normalized = " ".join((question or "").casefold().strip().split())
    if not normalized or normalized in _CASUAL_MESSAGES:
        return False
    if any(marker in normalized for marker in _FOLLOW_UP_MARKERS) and len(normalized) < 40:
        return False
    if normalized.endswith(("!", "！")) and "?" not in normalized and "؟" not in normalized:
        return False
    if "؟" in normalized or "?" in normalized:
        return True
    if normalized.startswith(_QUESTION_STARTERS):
        return True
    return any(token in normalized for token in _QUESTION_CONTEXT)


def _chunk_answer(text: str, size: int = _MAX_ANSWER_CHUNK) -> list[str]:
    text = text or ""
    if len(text) <= size:
        return [text]
    return [text[i : i + size] for i in range(0, len(text), size)]


async def _group_message_targets_bot(message: Message) -> bool:
    """Only let the AI assistant answer group messages when explicitly addressed."""
    chat_type = getattr(message.chat, "type", "")
    if chat_type not in {"group", "supergroup"}:
        return True

    bot_id = getattr(message.bot, "id", None)
    reply = message.reply_to_message
    if reply and reply.from_user and bot_id and reply.from_user.id == bot_id:
        return True

    text = message.text or ""
    for entity in message.entities or []:
        if entity.type == MessageEntityType.TEXT_MENTION and entity.user:
            if bot_id and entity.user.id == bot_id:
                return True
        if entity.type == MessageEntityType.MENTION:
            global _BOT_USERNAME
            if _BOT_USERNAME is None:
                try:
                    me = await message.bot.get_me()
                    _BOT_USERNAME = (me.username or "").casefold()
                except Exception:
                    _BOT_USERNAME = ""
            username = _BOT_USERNAME
            if username and text[entity.offset:entity.offset + entity.length].casefold() == f"@{username}":
                return True

    return False


def _remember_question(sent_message: Message | None, telegram_id: str, question: str) -> None:
    message_id = getattr(sent_message, "message_id", None)
    if message_id is None:
        return
    _recent_questions[int(message_id)] = (telegram_id, question)
    if len(_recent_questions) > _MAX_RECENT_QUESTIONS:
        oldest = next(iter(_recent_questions))
        _recent_questions.pop(oldest, None)


async def _answer_with_optional_progress(message: Message, db, user_message: str) -> str:
    """Run the model; only surface "در حال تحلیل" if the reply is slow."""
    await message.bot.send_chat_action(message.chat.id, "typing")
    work = asyncio.create_task(
        asyncio.to_thread(
            chat_assistant_service.answer,
            db,
            str(message.from_user.id),
            user_message,
        )
    )
    progress_msg: Message | None = None
    try:
        try:
            return await asyncio.wait_for(asyncio.shield(work), timeout=_SLOW_RESPONSE_SECONDS)
        except asyncio.TimeoutError:
            progress_msg = await message.answer("⏳ در حال تحلیل...")
            return await work
    finally:
        if progress_msg is not None:
            try:
                await progress_msg.delete()
            except Exception:
                pass


@router.message(F.text == MENU_BUTTON_TEXT)
async def chat_intro(message: Message):
    await message.answer(
        "🤖 <b>راه‌یار | دستیار هوشمند</b>\n\n"
        "سؤالت رو بپرس؛ جواب کوتاه و کاربردی می‌گیری.\n"
        "مثلاً: «چطور وکال را تمیزتر میکس کنم؟»\n"
        "DAW، Plugin، میکس، مستر، ضبط و تئوری موسیقی 🎚️\n\n"
        "<i>اگر لازم باشه، منابع معتبر وب هم بررسی می‌شن.</i>",
        parse_mode="HTML",
        reply_markup=ASSISTANT_HINTS,
    )


@router.message(StateFilter(None), F.text)
async def chat_fallback(message: Message, db):
    if not await _group_message_targets_bot(message):
        return

    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ اول /start رو بزن.")
        return

    try:
        reply = await _answer_with_optional_progress(message, db, message.text)
    except ChatAssistantError as exc:
        code = str(exc)
        if code == "empty_message":
            return
        if "تعداد پیام" in code:
            await message.answer(f"⏳ <b>محدودیت موقت</b>\n\n{code}", parse_mode="HTML")
            return
        await message.answer(DISABLED_MESSAGE_FA, parse_mode="HTML")
        return

    formatted = format_assistant_answer(reply)
    chunks = _chunk_answer(formatted)
    question_like = should_show_feedback(message.text)
    sent_message = None
    for index, part in enumerate(chunks):
        is_last = index == len(chunks) - 1
        # Feedback only on the final complete answer message — never on mid-chunks.
        keyboard = assistant_feedback_keyboard() if (question_like and is_last) else None
        sent_message = await message.answer(
            part,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
    if question_like and sent_message is not None:
        _remember_question(sent_message, str(message.from_user.id), message.text)


@router.callback_query(F.data.startswith("assistant_feedback:"))
async def assistant_feedback(callback):
    value = callback.data.rsplit(":", 1)[-1]
    text = "بازخورد شما ثبت شد؛ ممنون." if value == "up" else "ممنون؛ پاسخ‌های بعدی را دقیق‌تر می‌کنیم."
    await callback.answer(text)


@router.callback_query(F.data == "assistant_retry")
async def assistant_retry(callback, db):
    source = _recent_questions.get(getattr(callback.message, "message_id", -1))
    if not source:
        await callback.answer("برای پاسخ بهتر، سؤال را دوباره بفرستید.", show_alert=True)
        return
    telegram_id, question = source
    await callback.answer("⏳ در حال ساخت پاسخ بهتر...")
    try:
        work = asyncio.create_task(
            asyncio.to_thread(chat_assistant_service.answer, db, telegram_id, question)
        )
        try:
            reply = await asyncio.wait_for(asyncio.shield(work), timeout=_SLOW_RESPONSE_SECONDS)
            progress_msg = None
        except asyncio.TimeoutError:
            progress_msg = await callback.message.answer("⏳ در حال تحلیل...")
            reply = await work
        if progress_msg is not None:
            try:
                await progress_msg.delete()
            except Exception:
                pass
    except ChatAssistantError:
        await callback.message.answer("فعلاً امکان تولید پاسخ جدید نیست.")
        return

    formatted = format_assistant_answer(reply)
    chunks = _chunk_answer(formatted)
    sent_message = None
    for index, part in enumerate(chunks):
        is_last = index == len(chunks) - 1
        sent_message = await callback.message.answer(
            part,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=assistant_feedback_keyboard() if is_last else None,
        )
    if sent_message is not None:
        _remember_question(sent_message, telegram_id, question)
