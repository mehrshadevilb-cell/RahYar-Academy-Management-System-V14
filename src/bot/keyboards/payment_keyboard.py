from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def buy_keyboard(course_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 خرید دوره",
                    callback_data=f"buy_{course_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎁 دارم کد تخفیف",
                    callback_data=f"discount_{course_id}",
                )
            ],
        ]
    )


def receipt_waiting_keyboard() -> InlineKeyboardMarkup:
    """Shown while the student is expected to upload a card-to-card receipt."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ پرداخت کردم — ارسال رسید",
                    callback_data="pay_confirm_paid",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ انصراف از خرید",
                    callback_data="pay_cancel",
                )
            ],
        ]
    )
