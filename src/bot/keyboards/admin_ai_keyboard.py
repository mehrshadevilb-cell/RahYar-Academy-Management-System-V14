from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_ai_keyboard() -> InlineKeyboardMarkup:
    """Single coherent AI Developer control surface (no duplicate audits)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Assistant", callback_data="ai_assistant"),
                InlineKeyboardButton(text="🐞 Debug", callback_data="ai_debug"),
            ],
            [
                InlineKeyboardButton(text="🔎 Audit کامل", callback_data="ai_analyze:full"),
            ],
            [
                InlineKeyboardButton(text="🛠 Fix", callback_data="ai_fix"),
                InlineKeyboardButton(text="✨ Feature", callback_data="ai_feature"),
            ],
            [
                InlineKeyboardButton(text="🩺 Diagnostics", callback_data="ai_diagnostics"),
                InlineKeyboardButton(text="🧪 Test Models", callback_data="ai_test_models"),
            ],
            [
                InlineKeyboardButton(text="🔐 Guardrails", callback_data="ai_security"),
                InlineKeyboardButton(text="📋 Task Status", callback_data="ai_task_status"),
            ],
            [InlineKeyboardButton(text="🛑 Stop Task", callback_data="ai_stop")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")],
        ]
    )
