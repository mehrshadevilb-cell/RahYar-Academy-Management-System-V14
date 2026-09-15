from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_ai_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 دستیار", callback_data="ai_assistant"
                ),
                InlineKeyboardButton(text="🔎 Audit", callback_data="ai_analyze"),
            ],
            [
                InlineKeyboardButton(text="🐞 دیباگ", callback_data="ai_debug"),
                InlineKeyboardButton(
                    text="🎨 زیباسازی UI", callback_data="ai_ui_polish"
                ),
            ],
            [
                InlineKeyboardButton(text="🛠 رفع باگ", callback_data="ai_fix"),
                InlineKeyboardButton(
                    text="✨ قابلیت جدید", callback_data="ai_feature"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎨 اعمال UI (کد)", callback_data="ai_ui_write"
                ),
                InlineKeyboardButton(
                    text="♻️ Refactor", callback_data="ai_refactor"
                ),
            ],
            [
                InlineKeyboardButton(text="🧩 Skills", callback_data="ai_skills"),
                InlineKeyboardButton(
                    text="🧪 تست API", callback_data="ai_status"
                ),
            ],
            [
                InlineKeyboardButton(text="🔐 امنیت", callback_data="ai_security"),
                InlineKeyboardButton(
                    text="👁 فعالیت Agent", callback_data="ai_activity"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🛑 توقف Task", callback_data="ai_stop"
                ),
            ],
            [
                InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home"),
            ],
        ]
    )
