"""Instant FAQ answers without LLM for common academy questions."""
from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

router = Router()

_FAQ: list[tuple[tuple[str, ...], str]] = [
    (
        ("لایسنس", "لایسس", "کد دوره", "اسپات", "spotplayer"),
        "🔑 لایسنس دوره‌های دیجیتال بعد از تأیید پرداخت در «🎓 دوره های من» نمایش داده می‌شود.\n"
        "اگر وضعیت ناموفق بود، از «🆘 پشتیبانی» پیام بگذارید.",
    ),
    (
        ("چطور پرداخت", "پرداخت کنم", "کارت به کارت", "کارت‌به‌کارت", "رسید"),
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
    (
        ("پشتیبانی", "کمک", "مشکل"),
        "🆘 از دکمه «پشتیبانی» در منوی اصلی تیکت بفرستید؛ پاسخ توسط آکادمی انجام می‌شود.",
    ),
]


def match_faq(text: str) -> str | None:
    raw = (text or "").strip().casefold()
    if len(raw) < 2 or len(raw) > 80:
        return None
    for keys, answer in _FAQ:
        if any(k.casefold() in raw for k in keys):
            return answer
    return None


@router.message(lambda m: bool(m.text) and match_faq(m.text) is not None)
async def faq_quick_answer(message: Message):
    answer = match_faq(message.text or "")
    if answer:
        await message.answer(answer, parse_mode="HTML")
