from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from src.services.course_service import CourseService
from src.database.models.course import ProductDeliveryType

from src.bot.keyboards.course_keyboard import course_keyboard
from src.bot.keyboards.payment_keyboard import buy_keyboard


router = Router()


course_service = CourseService()


async def _send_course_card(target, course, text, keyboard):
    """`target` is anything with .answer()/.answer_photo() - a Message
    or a CallbackQuery's .message. Telegram photo captions are capped
    at 1024 chars; these course cards are always well under that."""

    if course.thumbnail:
        await target.answer_photo(
            photo=course.thumbnail,
            caption=text,
            reply_markup=keyboard,
        )
    else:
        await target.answer(
            text=text,
            reply_markup=keyboard,
        )



@router.message(
    lambda message: message.text == "📚 دوره ها"
)
async def courses_handler(
    message: Message,
    db
):

    courses = course_service.get_courses(
        db
    )


    if not courses:

        await message.answer(
            "📚 در حال حاضر دوره‌ای موجود نیست."
        )

        return



    for course in courses:


        price = (
            f"{course.price:,} تومان"
            if course.price
            else "رایگان"
        )


        badge = (
            "🎧 دیجیتال (SpotPlayer)"
            if course.delivery_type == ProductDeliveryType.SPOTPLAYER
            else "📢 کانال تلگرام"
        )

        await _send_course_card(
            message,
            course,
            text=f"""
🎵 {course.title}


📝 {course.description or "بدون توضیحات"}


{badge}


💳 قیمت:
{price}
""",
            keyboard=course_keyboard(
                course.id
            ),
        )





@router.callback_query(
    F.data.startswith("course_")
)
async def course_detail(
    callback: CallbackQuery,
    db
):

    course_id = int(
        callback.data.replace(
            "course_",
            ""
        )
    )



    courses = course_service.get_courses(
        db
    )


    course = next(
        (
            item
            for item in courses
            if item.id == course_id
        ),
        None
    )



    if not course:


        await callback.answer(
            "دوره پیدا نشد",
            show_alert=True
        )

        return



    await _send_course_card(
        callback.message,
        course,
        text=f"""
🎓 جزئیات دوره


🎵 عنوان:
{course.title}


📝 توضیحات:
{course.description or "بدون توضیحات"}


💳 قیمت:
{course.price:,} تومان
""",
        keyboard=buy_keyboard(
            course.id
        ),
    )


    await callback.answer()