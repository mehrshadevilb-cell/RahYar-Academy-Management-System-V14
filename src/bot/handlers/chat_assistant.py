"""Chat assistant: explicit entry point plus a minimal free-text fallback."""

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, KeyboardButton

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


def _remember_question(sent_message: Message | None, telegram_id: str, question: str) -> None:
    message_id = getattr(sent_message, "message_id", None)
    if message_id is None:
        return
    _recent_questions[int(message_id)] = (telegram_id, question)
    if len(_recent_questions) > _MAX_RECENT_QUESTIONS:
        oldest = next(iter(_recent_questions))
        _recent_questions.pop(oldest, None)


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
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ اول /start رو بزن.")
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
            await message.answer(f"⏳ <b>محدودیت موقت</b>\n\n{code}", parse_mode="HTML")
            return
        await message.answer(DISABLED_MESSAGE_FA, parse_mode="HTML")
        return

    sent_message = await message.answer(
        format_assistant_answer(reply),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=assistant_feedback_keyboard(),
    )
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
    try:
        reply = chat_assistant_service.answer(db=db, telegram_id=telegram_id, user_message=question)
    except ChatAssistantError:
        await callback.answer("فعلاً امکان تولید پاسخ جدید نیست.", show_alert=True)
        return
    sent_message = await callback.message.answer(
        format_assistant_answer(reply),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=assistant_feedback_keyboard(),
    )
    _remember_question(sent_message, telegram_id, question)
    await callback.answer("پاسخ جدید آماده شد.")
