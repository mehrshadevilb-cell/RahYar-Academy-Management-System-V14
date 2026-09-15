from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_ai_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 دستیار کدنویسی", callback_data="ai_assistant"
                ),
                InlineKeyboardButton(text="🛠 دیباگ ربات", callback_data="ai_debug"),
            ],
            [
                InlineKeyboardButton(
                    text="🎨 زیباسازی UI", callback_data="ai_ui_polish"
                ),
                InlineKeyboardButton(
                    text="🌐 جستجوی وب", callback_data="ai_research"
                ),
            ],
            [
                InlineKeyboardButton(text="🧠 وضعیت Agent", callback_data="ai_status"),
                InlineKeyboardButton(text="🔎 Audit", callback_data="ai_analyze"),
            ],
            [
                InlineKeyboardButton(text="🧩 Skills", callback_data="ai_skills"),
                InlineKeyboardButton(
                    text="✨ افزودن Feature", callback_data="ai_feature"
                ),
            ],
            [
                InlineKeyboardButton(text="🐞 رفع باگ (کد)", callback_data="ai_fix"),
                InlineKeyboardButton(
                    text="🎨 اعمال UI (کد)", callback_data="ai_ui_write"
                ),
            ],
            [
                InlineKeyboardButton(text="🛑 توقف / خروج چت", callback_data="ai_stop"),
            ],
            [
                InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home"),
            ],
        ]
    )
