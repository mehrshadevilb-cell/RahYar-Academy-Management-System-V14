from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.bot.keyboards.class_slot_keyboard import student_slots_keyboard
from src.bot.keyboards.reservation_review_keyboard import reservation_review_keyboard

from src.services.class_slot_service import ClassSlotServiceError
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.reservation_service import ReservationService
from src.services.profile_service import ProfileService
from src.core.config.settings import get_settings


router = Router()

online_enrollment_service = OnlineEnrollmentService()
reservation_service = ReservationService()
profile_service = ProfileService()

settings = get_settings()


def _enrollment_keyboard(enrollment_id: int, can_reserve: bool):
    rows = []
    if can_reserve:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📅 رزرو از زمان‌های آزاد",
                    callback_data=f"reserve_{enrollment_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def _plan_fa(model_value: str) -> str:
    return {
        "weekly": "هفتگی (۱ جلسه در هر پرداخت)",
        "monthly": "ماهانه (معمولاً ۴ جلسه در هر پرداخت)",
        "term": "ترمی",
    }.get(model_value, model_value)


@router.message(F.text == "🎼 کلاس آنلاین")
async def online_class_menu(message: Message, db):

    user = profile_service.get_profile(
        db=db, telegram_id=str(message.from_user.id)
    )

    if not user:
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    enrollments = online_enrollment_service.get_active_by_user(db, user.id)

    if not enrollments:
        await message.answer(
            "شما در حال حاضر در هیچ کلاس آنلاینی ثبت‌نام نشده‌اید.\n"
            "برای ثبت‌نام با پشتیبانی آکادمی در ارتباط باشید."
        )
        return

    for enrollment in enrollments:
        status_fa = {
            "active": "فعال",
            "paused": "⏸ در انتظار پرداخت دوره بعد",
            "ended": "پایان‌یافته",
        }.get(enrollment.status.value, enrollment.status.value)

        can_reserve = (
            enrollment.status.value == "active"
            and enrollment.remaining_sessions > 0
        )

        text = (
            f"🎼 {enrollment.online_course.name}\n\n"
            f"نوع پرداخت: {_plan_fa(enrollment.payment_model.value)}\n"
            f"وضعیت: {status_fa}\n"
            f"جلسات باقی‌مانده قابل رزرو: {enrollment.remaining_sessions}\n"
            f"جلسات برگزار شده: {enrollment.completed_sessions}"
        )
        if enrollment.status.value == "paused":
            text += (
                "\n\n⚠️ جلسات این دوره تمام شده. "
                "پس از تأیید پرداخت دوره بعد، دوباره می‌توانید از لیست زمان‌های آزاد رزرو کنید."
            )

        await message.answer(
            text=text,
            reply_markup=_enrollment_keyboard(enrollment.id, can_reserve),
        )


@router.callback_query(F.data.startswith("reserve_"))
async def reservation_start(callback: CallbackQuery, db):

    enrollment_id = int(callback.data.replace("reserve_", ""))

    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))

    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return

    if enrollment.status.value != "active" or enrollment.remaining_sessions <= 0:
        await callback.answer(
            "جلسه قابل رزرو ندارید. ابتدا پرداخت دوره را تکمیل کنید.",
            show_alert=True,
        )
        return

    from src.services.class_slot_service import ClassSlotService

    slots = ClassSlotService().list_open_for_course(db, enrollment.online_course_id)
    if not slots:
        await callback.message.answer(
            "فعلاً زمان آزادی برای این کلاس در لیست آکادمی ثبت نشده است.\n"
            "لطفاً بعداً دوباره سر بزنید یا با پشتیبانی هماهنگ کنید."
        )
        await callback.answer()
        return

    await callback.message.answer(
        "یکی از زمان‌های آزاد زیر را انتخاب کنید:",
        reply_markup=student_slots_keyboard(enrollment_id, slots),
    )
    await callback.answer()


@router.callback_query(F.data == "slot_cancel")
async def slot_cancel(callback: CallbackQuery):
    await callback.message.edit_text("رزرو لغو شد.")
    await callback.answer()


@router.callback_query(F.data.startswith("slot_pick_"))
async def slot_pick(callback: CallbackQuery, bot: Bot, db):
    # slot_pick_{enrollment_id}_{slot_id}
    parts = callback.data.replace("slot_pick_", "").split("_")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        await callback.answer("داده نامعتبر", show_alert=True)
        return

    enrollment_id, slot_id = int(parts[0]), int(parts[1])
    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))

    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️", show_alert=True)
        return

    if enrollment.status.value != "active" or enrollment.remaining_sessions <= 0:
        await callback.answer("جلسه قابل رزرو ندارید.", show_alert=True)
        return

    try:
        reservation = reservation_service.request_from_slot(
            db, enrollment_id=enrollment_id, slot_id=slot_id
        )
    except ClassSlotServiceError as exc:
        mapping = {
            "slot_unavailable": "این زمان دیگر آزاد نیست.",
            "already_requested": "برای این زمان قبلاً درخواست باز دارید.",
        }
        await callback.answer(mapping.get(str(exc), "رزرو ناموفق"), show_alert=True)
        return

    student = profile_service.get_profile_by_id(db, enrollment.user_id)

    await callback.message.edit_text(
        f"✅ درخواست رزرو ثبت شد.\n"
        f"📆 {reservation.requested_date} — ⏰ {reservation.requested_time}\n"
        "پس از تأیید ادمین مطلع می‌شوید."
    )
    await callback.answer()

    if settings.OWNER_ID:
        await bot.send_message(
            chat_id=settings.OWNER_ID,
            text=(
                f"📅 درخواست رزرو از لیست زمان‌های آزاد\n\n"
                f"🎼 کلاس: {enrollment.online_course.name}\n"
                f"👤 هنرجو: {student.full_name if student else enrollment.user_id}\n"
                f"📆 {reservation.requested_date}\n"
                f"⏰ {reservation.requested_time}"
            ),
            reply_markup=reservation_review_keyboard(reservation.id),
        )
