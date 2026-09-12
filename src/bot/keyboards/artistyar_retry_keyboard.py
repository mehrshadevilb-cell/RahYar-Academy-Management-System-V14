from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def artistyar_retry_keyboard(user_id: int, product_id: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔁 تلاش مجدد",
                    callback_data=f"artistyar_retry_{user_id}_{product_id}",
                ),
            ]
        ]
    )
