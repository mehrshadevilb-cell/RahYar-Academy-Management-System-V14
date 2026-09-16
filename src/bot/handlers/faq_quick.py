"""Instant FAQ answers without LLM for common academy questions."""
from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

router = Router()

_MENU_BUTTONS = {
    "📚 دوره ها",
    "🎓 دوره های من",
    "🎼 کلاس آنلاین",
    "🎵 AI Generator",
    "📝 تکالیف",
    "📈 پیشرفت من",
    "👤 پروفایل",
    "🎁 دعوت از دوستان",
    "🤖 دستیار هوشمند",
    "🆘 پشتیبانی",
    "🛠 پنل مدیریت",
}

_FAQ: list[tuple[tuple[str, ...], str]] = [
    (
        ("لایسنس", "لایسس", "کد دوره", "اسپات", "spotplayer"),
        "🔑 لایسنس دوره‌های دیجیتال بعد از تأیید پرداخت در «🎓 دوره های من» نمایش داده می‌شود.\n"
        "اگر وضعیت ناموفق بود، از «🆘 پشتیبانی» پیام بگذارید.",
    ),
    (
        ("چطور پرداخت", "پرداخت کنم", "کارت به کارت", "کارت‌به‌کارت", "رسید پرداخت"),
        "💳 برای خرید: «📚 دوره ها» → انتخاب دوره → کارت‌به‌کارت → ارسال <b>عکس رسید</b>.\n"
        "تا تأیید ادمین، دسترسی فعال نمی‌شود.",
    ),
    (
        ("کلاس آنلاین", "رزرو کلاس", "ساعت کلاس"),
        "🎼 از منوی «کلاس آنلاین» دوره و زمان را انتخاب کنید.\n"
        "رزرو طبق قوانین آکادمی و ظرفیت باقی‌مانده ثبت می‌شود.",
    ),
    (
        ("اقساط", "قسط"),
        "💰 وضعیت اقساط از پنل ادمین مدیریت می‌شود. یادآوری‌ها طبق تنظیمات آکادمی ارسال می‌شوند.",
    ),
]


def match_faq(text: str) -> str | None:
    raw = (text or "").strip()
    if raw in _MENU_BUTTONS:
        return None
    lowered = raw.casefold()
    if len(lowered) < 2 or len(lowered) > 80:
        return None
    for keys, answer in _FAQ:
        if any(k.casefold() in lowered for k in keys):
            return answer
    return None


@router.message(lambda m: bool(m.text) and match_faq(m.text) is not None)
async def faq_quick_answer(message: Message):
    answer = match_faq(message.text or "")
    if answer:
        await message.answer(answer, parse_mode="HTML")
