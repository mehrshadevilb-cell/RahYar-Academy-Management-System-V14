from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def broadcast_confirm_keyboard(audience_count: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ ارسال به {audience_count:,} نفر",
                    callback_data="admin_broadcast_confirm",
                ),
            ],
            [
                InlineKeyboardButton(text="❌ انصراف", callback_data="admin_broadcast_cancel"),
            ],
        ]
    )
