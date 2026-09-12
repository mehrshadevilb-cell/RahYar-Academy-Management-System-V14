from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def reservation_review_keyboard(reservation_id: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ تایید",
                    callback_data=f"res_confirm_{reservation_id}",
                ),
                InlineKeyboardButton(
                    text="❌ رد",
                    callback_data=f"res_reject_{reservation_id}",
                ),
            ]
        ]
    )
