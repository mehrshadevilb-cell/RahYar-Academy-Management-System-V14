from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def license_retry_keyboard(license_id: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔁 تلاش مجدد",
                    callback_data=f"license_retry_{license_id}",
                ),
            ]
        ]
    )
