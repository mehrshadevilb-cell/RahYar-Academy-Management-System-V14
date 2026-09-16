"""Chat assistant: explicit entry point plus a minimal free-text fallback."""

from collections import defaultdict, deque

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
# Short conversation memory: last few turns per telegram user (in-process).
_conversation: dict[str, deque[tuple[str, str]]] = defaultdict(lambda: deque(maxlen=4))
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

# Instant answers — no model call.
_FAST_ANSWERS: dict[str, str] = {
    "سلام": "سلام 👋 من دستیار راه‌یار هستم. سؤالت درباره DAW، پلاگین، میکس یا دوره‌ها رو بپرس.",
    "درود": "درود! چطور می‌تونم کمکت کنم؟",
    "hi": "Hi! Ask about DAW, plugins, mix, or academy courses.",
    "hello": "Hello! How can I help with music production or your course?",
    "مرسی": "خواهش می‌کنم 🙏",
    "ممنون": "خواهش می‌کنم 🙏",
    "thanks": "You're welcome.",
    "خداحافظ": "خداحافظ؛ موفق باشی 🎵",
    "bye": "Bye!",
}

_MENU_HELP = (
    "منوی اصلی:\n"
    "• 📚 دوره ها — خرید دوره دیجیتال\n"
    "• 🎓 دوره های من — دسترسی‌های شما\n"
    "• 🎼 کلاس آنلاین — رزرو کلاس زنده\n"
    "• 📝 تکالیف / 📈 پیشرفت من\n"
    "• 🆘 پشتیبانی — پیام به مدیریت\n"
    "• 🔔 اعلان‌ها — خاموش/روشن کردن یادآورها"
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
    normalized = " ".join((question or "").casefold().strip().split())
    if not normalized or normalized in _CASUAL_MESSAGES:
        return False
    if any(m in normalized for m in _FOLLOW_UP_MARKERS) and len(normalized) < 40:
        return False
    if normalized.endswith(("!", "！")) and "?" not in normalized and "؟" not in normalized:
        return False
    if "؟" in normalized or "?" in normalized:
        return True
    if normalized.startswith(_QUESTION_STARTERS):
        return True
    return any(token in normalized for token in _QUESTION_CONTEXT)


def try_fast_answer(text: str) -> str | None:
    normalized = " ".join((text or "").casefold().strip().split())
    if normalized in _FAST_ANSWERS:
        return _FAST_ANSWERS[normalized]
    if any(t in normalized for t in ("منو", "راهنمای ربات", "دکمه‌ها", "چیکار میشه")):
        return _MENU_HELP
    if normalized in ("راهنمای daw", "🎚️ راهنمای daw"):
        return "برای DAW بگو کدوم نرم‌افزار و نسخه (مثلاً Cubase 13 یا Ableton 12) تا مسیر منو و تنظیم دقیق بدم."
    if normalized in ("راهنمای plugin", "🎛️ راهنمای plugin"):
        return "نام پلاگین و کاری که می‌خوای (مثلاً de-ess وکال با Waves) رو بگو."
    if normalized in ("تئوری موسیقی", "🎼 تئوری موسیقی"):
        return "سؤالت رو مشخص کن: گام، آکورد، فاصله، ریتم یا هارمونی؟"
    return None


def _remember_question(sent_message: Message | None, telegram_id: str, question: str) -> None:
    message_id = getattr(sent_message, "message_id", None)
    if message_id is None:
        return
    _recent_questions[int(message_id)] = (telegram_id, question)
    if len(_recent_questions) > _MAX_RECENT_QUESTIONS:
        oldest = next(iter(_recent_questions))
        _recent_questions.pop(oldest, None)


def _history_prompt(telegram_id: str) -> str:
    turns = list(_conversation.get(telegram_id) or [])
    if not turns:
        return ""
    lines = ["گفتگوی اخیر (برای ادامه):"]
    for q, a in turns[-3:]:
        lines.append(f"کاربر: {q[:200]}")
        lines.append(f"دستیار: {a[:300]}")
    return "\n".join(lines)


def _store_turn(telegram_id: str, question: str, answer: str) -> None:
    _conversation[telegram_id].append((question, answer))


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

    tid = str(message.from_user.id)
    text = message.text or ""

    fast = try_fast_answer(text)
    if fast is not None:
        await message.answer(format_assistant_answer(fast), parse_mode="HTML")
        _store_turn(tid, text, fast)
        return

    await message.bot.send_chat_action(message.chat.id, "typing")
    history = _history_prompt(tid)
    user_message = text if not history else f"{history}\n\nسؤال فعلی:\n{text}"
    try:
        reply = chat_assistant_service.answer(
            db=db,
            telegram_id=tid,
            user_message=user_message,
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

    _store_turn(tid, text, reply)
    question_like = should_show_feedback(text)
    sent_message = await message.answer(
        format_assistant_answer(reply),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=assistant_feedback_keyboard() if question_like else None,
    )
    if question_like:
        _remember_question(sent_message, tid, text)


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
