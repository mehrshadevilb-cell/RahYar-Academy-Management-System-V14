from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def attendance_keyboard(reservation_id: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ حاضر",
                    callback_data=f"att_present_{reservation_id}",
                ),
                InlineKeyboardButton(
                    text="❌ غایب",
                    callback_data=f"att_absent_{reservation_id}",
                ),
                InlineKeyboardButton(
                    text="🚫 لغو شده",
                    callback_data=f"att_cancelled_{reservation_id}",
                ),
            ]
        ]
    )
