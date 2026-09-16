from aiogram import Router
from aiogram.types import Message

from src.services.notification_preference_service import (
    CATEGORY_LABELS_FA,
    NotificationPreferenceService,
)
from src.services.profile_service import ProfileService

router = Router()
profile_service = ProfileService()
pref_service = NotificationPreferenceService()


@router.message(lambda message: message.text == "👤 پروفایل")
async def profile_handler(message: Message, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ پروفایل شما پیدا نشد.")
        return

    role_text = "مدیر" if user.role.value == "admin" else "هنرجو"
    pref = pref_service.get_or_create(db, user.id)
    prefs = pref_service.as_dict(pref)
    notif_lines = []
    for key, label in CATEGORY_LABELS_FA.items():
        notif_lines.append(f"{'✅' if prefs.get(key, True) else '🔕'} {label}")

    await message.answer(
        "👤 <b>پروفایل شما</b>\n\n"
        f"نام: {user.full_name}\n"
        f"نقش: {role_text}\n"
        f"وضعیت: {'فعال' if user.is_active else 'غیرفعال'}\n"
        f"تاریخ عضویت: {user.created_at.strftime('%Y-%m-%d')}\n\n"
        "🔔 اعلان‌ها:\n"
        + "\n".join(notif_lines)
        + "\n\n<i>برای تغییر از منوی «🔔 اعلان‌ها» استفاده کنید.</i>",
        parse_mode="HTML",
    )
