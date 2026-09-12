from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_logs_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 جستجو در لاگ‌ها", callback_data="admin_logs_search")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")],
        ]
    )
