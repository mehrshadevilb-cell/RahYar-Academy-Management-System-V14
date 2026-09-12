from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def payment_review_keyboard(payment_id: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ تایید",
                    callback_data=f"pay_approve_{payment_id}",
                ),
                InlineKeyboardButton(
                    text="❌ رد",
                    callback_data=f"pay_reject_{payment_id}",
                ),
            ]
        ]
    )
