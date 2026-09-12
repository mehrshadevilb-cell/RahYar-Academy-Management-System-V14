from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_cards_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ افزودن کارت جدید", callback_data="admin_card_add")],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")],
        ]
    )
