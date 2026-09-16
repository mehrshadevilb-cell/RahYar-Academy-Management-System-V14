"""Student notification mute settings."""
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.notification_keyboard import notification_settings_keyboard
from src.services.notification_preference_service import (
    CATEGORY_LABELS_FA,
    NotificationPreferenceService,
)
from src.services.profile_service import ProfileService

router = Router()
profile_service = ProfileService()
pref_service = NotificationPreferenceService()


def _prefs_text(prefs: dict[str, bool]) -> str:
    lines = ["🔔 <b>تنظیمات اعلان‌ها</b>", "━━━━━━━━━━━━━━━━━━", ""]
    for key, label in CATEGORY_LABELS_FA.items():
        enabled = prefs.get(key, True)
        lines.append(f"{'✅' if enabled else '🔕'} {label}: {'فعال' if enabled else 'غیرفعال'}")
    lines.append("")
    lines.append("<i>روی هر مورد بزنید تا روشن/خاموش شود.</i>")
    return "\n".join(lines)


@router.message(F.text == "🔔 اعلان‌ها")
async def open_notification_settings(message: Message, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ اول /start رو بزن.")
        return
    pref = pref_service.get_or_create(db, user.id)
    prefs = pref_service.as_dict(pref)
    await message.answer(
        _prefs_text(prefs),
        parse_mode="HTML",
        reply_markup=notification_settings_keyboard(prefs),
    )


@router.callback_query(F.data.startswith("notif_toggle:"))
async def toggle_notification(callback: CallbackQuery, db):
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not user:
        await callback.answer("پروفایل پیدا نشد.", show_alert=True)
        return
    category = callback.data.split(":", 1)[-1]
    try:
        pref = pref_service.toggle(db, user.id, category)
    except ValueError:
        await callback.answer("دسته نامعتبر", show_alert=True)
        return
    prefs = pref_service.as_dict(pref)
    label = CATEGORY_LABELS_FA.get(category, category)
    enabled = prefs.get(category, True)
    await callback.message.edit_text(
        _prefs_text(prefs),
        parse_mode="HTML",
        reply_markup=notification_settings_keyboard(prefs),
    )
    await callback.answer(f"{label} {'فعال' if enabled else 'غیرفعال'} شد")


@router.callback_query(F.data == "notif_back_profile")
async def back_to_profile(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("برای مشاهده پروفایل از منوی «👤 پروفایل» استفاده کنید.")
