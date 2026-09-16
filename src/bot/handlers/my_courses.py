from aiogram import Router
from aiogram.types import Message

from src.services.enrollment_service import EnrollmentService
from src.services.profile_service import ProfileService
from src.database.repositories.course_repository import CourseRepository
from src.database.repositories.payment_repository import PaymentRepository


router = Router()


enrollment_service = EnrollmentService()

profile_service = ProfileService()
course_repository = CourseRepository()
payment_repository = PaymentRepository()



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


@router.message(lambda message: message.text == "🧾 وضعیت پرداخت")
async def payment_status_handler(message: Message, db):
    user = profile_service.get_profile(
        db=db,
        telegram_id=str(message.from_user.id),
    )
    if not user:
        await message.answer("❌ کاربر پیدا نشد. لطفاً دوباره /start را بزنید.")
        return

    payments = payment_repository.get_for_user(db, user.id)
    if not payments:
        await message.answer("🧾 هنوز پرداختی برای حساب شما ثبت نشده است.")
        return

    labels = {
        "pending": "در انتظار بررسی",
        "approved": "تأیید شده",
        "rejected": "رد شده",
        "cancelled": "لغو شده",
    }
    lines = ["🧾 وضعیت آخرین پرداخت‌ها:\n"]
    for payment in payments:
        course = course_repository.get_by_id(db, payment.course_id)
        title = course.title if course else f"محصول #{payment.course_id}"
        status = labels.get(payment.status, payment.status)
        lines.append(
            f"#{payment.id} · {title}\n"
            f"مبلغ: {payment.amount:,} تومان\n"
            f"وضعیت: {status}\n"
        )
    lines.append("برای پیگیری سریع‌تر، شماره پرداخت را نگه دارید.")
    await message.answer("\n".join(lines))
