"""Chat assistant: explicit entry point plus a minimal free-text fallback."""

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

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
    one_time_keyboard=True,
    input_field_placeholder="سؤالت رو بنویس…",
)


@router.message(F.text == MENU_BUTTON_TEXT)
async def chat_intro(message: Message):
    await message.answer(
        "🤖 <b>راه‌یار | دستیار هوشمند</b>\n\n"
        "سؤالت رو بپرس؛ جواب کوتاه و کاربردی می‌گیری.\n"
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

    await message.answer(
        format_assistant_answer(reply),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
