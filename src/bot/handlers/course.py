from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from src.services.course_service import CourseService
from src.database.models.course import ProductDeliveryType

from src.bot.keyboards.course_keyboard import course_keyboard
from src.bot.keyboards.payment_keyboard import buy_keyboard


router = Router()


course_service = CourseService()



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

        await message.answer(

            text=f"""
🎵 {course.title}


📝 {course.description or "بدون توضیحات"}


{badge}


💳 قیمت:
{price}
""",

            reply_markup=course_keyboard(
                course.id
            )

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



    await callback.message.answer(

        text=f"""
🎓 جزئیات دوره


🎵 عنوان:
{course.title}


📝 توضیحات:
{course.description or "بدون توضیحات"}


💳 قیمت:
{course.price:,} تومان
""",

        reply_markup=buy_keyboard(
            course.id
        )

    )


    await callback.answer()