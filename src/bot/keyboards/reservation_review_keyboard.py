from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def reservation_review_keyboard(reservation_id: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 تایید پرداخت و رزرو زمان",
                    callback_data=f"res_payment_confirm_{reservation_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ رد پرداخت",
                    callback_data=f"res_payment_reject_{reservation_id}",
                ),
            ]
        ]
    )
