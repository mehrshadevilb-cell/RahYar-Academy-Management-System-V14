from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_ai_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🧠 وضعیت Agent", callback_data="ai_status"),
                InlineKeyboardButton(text="🔎 Audit", callback_data="ai_analyze"),
            ],
            [
                InlineKeyboardButton(text="🐞 پیدا کردن/رفع باگ", callback_data="ai_fix"),
                InlineKeyboardButton(text="✨ افزودن Feature", callback_data="ai_feature"),
            ],
            [
                InlineKeyboardButton(text="🛑 توقف", callback_data="ai_stop"),
            ],
            [
                InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home"),
            ],
        ]
    )
