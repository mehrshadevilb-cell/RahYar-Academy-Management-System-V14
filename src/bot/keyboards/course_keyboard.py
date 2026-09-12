from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)



def course_keyboard(
    course_id: int
):

    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="🎓 مشاهده دوره",

                    callback_data=f"course_{course_id}"

                )

            ]

        ]

    )