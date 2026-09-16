from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.notification_preference_service import CATEGORY_LABELS_FA


def notification_settings_keyboard(prefs: dict[str, bool]) -> InlineKeyboardMarkup:
    rows = []
    for key, label in CATEGORY_LABELS_FA.items():
        enabled = prefs.get(key, True)
        icon = "✅" if enabled else "🔕"
        state = "فعال" if enabled else "غیرفعال"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} {label}: {state}",
                    callback_data=f"notif_toggle:{key}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به پروفایل", callback_data="notif_back_profile")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
