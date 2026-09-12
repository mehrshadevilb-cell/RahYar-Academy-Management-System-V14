from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def installment_review_keyboard(installment_id: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ ثبت پرداخت",
                    callback_data=f"inst_paid_{installment_id}",
                ),
            ]
        ]
    )
