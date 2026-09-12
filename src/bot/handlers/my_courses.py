from aiogram import Router
from aiogram.types import Message

from src.services.enrollment_service import EnrollmentService
from src.services.profile_service import ProfileService


router = Router()


enrollment_service = EnrollmentService()

profile_service = ProfileService()



@router.message(
    lambda message: message.text == "🎓 دوره های من"
)
async def my_courses_handler(
    message: Message,
    db
):


    telegram_id = str(
        message.from_user.id
    )


    user = profile_service.get_profile(
        db=db,
        telegram_id=telegram_id
    )


    if not user:

        await message.answer(
            "❌ کاربر پیدا نشد"
        )

        return



    courses = enrollment_service.get_user_courses(
        db=db,
        user_id=user.id
    )


    if not courses:

        await message.answer(
            "📚 هنوز هیچ دوره‌ای خریداری نکرده‌اید."
        )

        return



    text = "🎓 دوره‌های شما:\n\n"



    for course in courses:

        text += f"""
🎵 {course.title}

📝 {course.description or "بدون توضیحات"}

----------------
"""


    await message.answer(
        text
    )