from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)



def buy_keyboard(
    course_id: int
):

    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(
                    text="💳 خرید دوره",
                    callback_data=f"buy_{course_id}"
                )

            ],

            [

                InlineKeyboardButton(
                    text="🎁 دارم کد تخفیف",
                    callback_data=f"discount_{course_id}"
                )

            ]

        ]

    )