from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_ai_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Assistant", callback_data="ai_assistant"),
                InlineKeyboardButton(text="🔎 Audit", callback_data="ai_analyze"),
            ],
            [
                InlineKeyboardButton(text="🐞 Debug", callback_data="ai_debug"),
                InlineKeyboardButton(text="🛠 Fix", callback_data="ai_fix"),
            ],
            [
                InlineKeyboardButton(text="✨ Feature", callback_data="ai_feature"),
                InlineKeyboardButton(text="🧪 Test API", callback_data="ai_status"),
            ],
            [
                InlineKeyboardButton(text="🔐 Security", callback_data="ai_security"),
                InlineKeyboardButton(text="📋 Task Status", callback_data="ai_task_status"),
            ],
            [InlineKeyboardButton(text="🛑 Stop Task", callback_data="ai_stop")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")],
        ]
    )
