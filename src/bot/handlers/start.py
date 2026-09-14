from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from src.bot.keyboards.main_menu import get_main_menu
from src.database.repositories.course_repository import CourseRepository
from src.services.online_course_service import OnlineCourseService
from src.services.referral_service import ReferralService
from src.services.telegram_service import TelegramService

router = Router()

telegram_service = TelegramService()
referral_service = ReferralService()
course_repository = CourseRepository()
online_course_service = OnlineCourseService()

REFERRAL_PAYLOAD_PREFIX = "ref_"
BUY_PAYLOAD_PREFIX = "buy_"
CLASS_PAYLOAD_PREFIX = "class_"


@router.message(Command("start"))
async def start_handler(
    message: Message,
    command: CommandObject,
    db,
):

    user, is_new = telegram_service.get_or_create_user(
        db=db,
        telegram_id=str(message.from_user.id),
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )

    args = (command.args or "").strip()

    if is_new and args.startswith(REFERRAL_PAYLOAD_PREFIX):
        referrer_telegram_id = args[len(REFERRAL_PAYLOAD_PREFIX):]
        referral_service.create_referral_if_eligible(
            db=db,
            referrer_telegram_id=referrer_telegram_id,
            referred_user_id=user.id,
        )

    await message.answer(
        f"سلام {user.full_name} 👋\n"
        "به آکادمی راه‌یار خوش آمدید.",
        reply_markup=get_main_menu(user.role),
    )

    # Deep links from the public website (same catalog / same bot).
    if args.startswith(BUY_PAYLOAD_PREFIX):
        raw_id = args[len(BUY_PAYLOAD_PREFIX):]
        if raw_id.isdigit():
            product = course_repository.get_by_id(db, int(raw_id))
            if product and product.is_active:
                await message.answer(
                    f"🛒 ادامه خرید از وب‌سایت\n\n"
                    f"محصول: {product.title}\n"
                    f"قیمت: {product.price:,} تومان\n\n"
                    "از منوی «📚 دوره ها» محصول را انتخاب کنید و رسید کارت‌به‌کارت را بفرستید.\n"
                    "تا قبل از تأیید مالک، دسترسی فعال نمی‌شود."
                )
                return

    if args.startswith(CLASS_PAYLOAD_PREFIX):
        raw_id = args[len(CLASS_PAYLOAD_PREFIX):]
        if raw_id.isdigit():
            course = online_course_service.get_course_by_id(db, int(raw_id))
            if course and course.is_active:
                await message.answer(
                    f"🎼 کلاس آنلاین از وب‌سایت\n\n"
                    f"کلاس: {course.name}\n"
                    f"مدرس: {course.teacher or '—'}\n\n"
                    "از منوی «🎼 کلاس آنلاین» می‌توانید وضعیت ثبت‌نام و رزرو را ببینید.\n"
                    "ثبت‌نام نهایی توسط آکادمی انجام می‌شود."
                )
