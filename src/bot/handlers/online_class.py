import re

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.bot.states.reservation_states import ReservationState
from src.bot.keyboards.reservation_review_keyboard import reservation_review_keyboard
from src.bot.keyboards.jalali_calendar_keyboard import jalali_calendar_keyboard

from src.services.online_course_service import OnlineCourseService
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.reservation_service import ReservationService
from src.services.profile_service import ProfileService
from src.services.online_schedule_service import OnlineScheduleService
from src.services.payment_card_service import PaymentCardService
from src.database.models.online_enrollment import PaymentModel
from src.database.repositories.telegram_repository import TelegramRepository
from src.core.config.settings import get_settings
from src.core.utils.jalali import (
    today_jalali,
    format_jalali_date,
    is_past_jalali_date,
    JALALI_MONTH_NAMES,
)


router = Router()

online_course_service = OnlineCourseService()
online_enrollment_service = OnlineEnrollmentService()
reservation_service = ReservationService()
schedule_service = OnlineScheduleService()
payment_card_service = PaymentCardService()
profile_service = ProfileService()
telegram_repository = TelegramRepository()

settings = get_settings()

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _enrollment_keyboard(enrollment_id: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 درخواست رزرو کلاس",
                    callback_data=f"reserve_{enrollment_id}",
                )
            ]
        ]
    )


def _slot_keyboard(enrollment_id: int, slots):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🕒 {slot.label}", callback_data=f"reserve_slot_{enrollment_id}_{slot.id}")]
        for slot in slots
    ])


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

        plan_text = (
            "ماهانه" if enrollment.payment_model.value == "monthly" else "ترمی"
        )

        await message.answer(
            text=f"""
🎼 {enrollment.online_course.name}

نوع پرداخت: {plan_text}
جلسات باقی‌مانده: {enrollment.remaining_sessions}
جلسات برگزار شده: {enrollment.completed_sessions}
""",
            reply_markup=_enrollment_keyboard(enrollment.id),
        )


@router.callback_query(F.data.startswith("reserve_"))
async def reservation_start(callback: CallbackQuery, state: FSMContext, db):

    enrollment_id = int(callback.data.replace("reserve_", ""))

    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))

    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return

    if enrollment.status.value != "active" or enrollment.remaining_sessions <= 0:
        await callback.answer("این کلاس دیگر جلسه قابل رزرو ندارد.", show_alert=True)
        return

    slots = schedule_service.list_active_slots(db, enrollment.online_course_id)
    if slots:
        await state.update_data(enrollment_id=enrollment_id)
        await callback.message.answer(
            "🕒 زمان هفتگی کلاس را انتخاب کنید:",
            reply_markup=_slot_keyboard(enrollment_id, slots),
        )
        await callback.answer()
        return

    await state.update_data(enrollment_id=enrollment_id)
    await state.set_state(ReservationState.waiting_date)

    jy, jm, _ = today_jalali()

    await callback.message.answer(
        "📅 تاریخ مورد نظر را از تقویم زیر انتخاب کنید:",
        reply_markup=jalali_calendar_keyboard(enrollment_id, jy, jm),
    )

    await callback.answer()


@router.callback_query(F.data == "jcal:noop")
async def jalali_calendar_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("reserve_slot_"))
async def reservation_slot_pick(callback: CallbackQuery, state: FSMContext, db):
    _, _, enrollment_raw, slot_raw = callback.data.split("_")
    enrollment_id, slot_id = int(enrollment_raw), int(slot_raw)
    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return
    slots = schedule_service.list_active_slots(db, enrollment.online_course_id)
    if not any(slot.id == slot_id for slot in slots):
        await callback.answer("این زمان دیگر فعال نیست.", show_alert=True)
        return
    await state.update_data(enrollment_id=enrollment_id, slot_id=slot_id)
    await state.set_state(ReservationState.waiting_date)
    jy, jm, _ = today_jalali()
    await callback.message.answer(
        "📅 تاریخ شروع رزرو را انتخاب کنید:",
        reply_markup=jalali_calendar_keyboard(enrollment_id, jy, jm),
    )
    await callback.answer()


@router.callback_query(
    ReservationState.waiting_date,
    F.data.startswith("jcal:nav:"),
)
async def jalali_calendar_navigate(callback: CallbackQuery, db):

    _, _, enrollment_id_raw, jy_raw, jm_raw = callback.data.split(":")
    enrollment_id, jy, jm = int(enrollment_id_raw), int(jy_raw), int(jm_raw)

    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)

    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return

    await callback.message.edit_reply_markup(
        reply_markup=jalali_calendar_keyboard(enrollment_id, jy, jm)
    )

    await callback.answer()


@router.callback_query(
    ReservationState.waiting_date,
    F.data.startswith("jcal:pick:"),
)
async def jalali_calendar_pick(callback: CallbackQuery, state: FSMContext, db):

    _, _, enrollment_id_raw, jy_raw, jm_raw, jd_raw = callback.data.split(":")
    enrollment_id, jy, jm, jd = int(enrollment_id_raw), int(jy_raw), int(jm_raw), int(jd_raw)

    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)

    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return

    if is_past_jalali_date(jy, jm, jd):
        await callback.answer("❌ این تاریخ گذشته است.", show_alert=True)
        return

    requested_date = format_jalali_date(jy, jm, jd)

    data = await state.get_data()
    slot_id = data.get("slot_id")
    if slot_id:
        count = enrollment.online_course.term_sessions if enrollment.payment_model == PaymentModel.TERM else enrollment.online_course.monthly_sessions
        try:
            reservations = schedule_service.create_jalali_reservation_plan(
                db, enrollment, int(slot_id), jy, jm, jd, min(count, enrollment.remaining_sessions)
            )
        except ValueError as exc:
            await state.clear()
            await callback.answer(str(exc), show_alert=True)
            return
        card = payment_card_service.get_active_card(db)
        await state.update_data(reservation_ids=[item.id for item in reservations])
        await state.set_state(ReservationState.waiting_receipt)
        plan_name = "ترمی" if enrollment.payment_model == PaymentModel.TERM else "ماهانه"
        card_text = f"\nشماره کارت: {card.card_number}\nبه نام: {card.card_holder}\n" if card else "\nفعلاً کارت پرداخت تنظیم نشده؛ با پشتیبانی تماس بگیرید.\n"
        await callback.message.edit_text(
            f"✅ برنامه {plan_name} برای {len(reservations)} جلسه ساخته شد.\n"
            f"از تاریخ {requested_date}، زمان انتخابی برای شما رزرو شده است.\n"
            f"برای نهایی شدن، رسید پرداخت را ارسال کنید.{card_text}"
        )
        await callback.answer()
        return

    await state.update_data(requested_date=requested_date)
    await state.set_state(ReservationState.waiting_time)

    await callback.message.edit_text(
        f"📅 تاریخ انتخابی: {jd} {JALALI_MONTH_NAMES[jm - 1]} {jy}\n\n"
        "⏰ ساعت مورد نظر را به فرمت 18:30 ارسال کنید:"
    )

    await callback.answer()


@router.message(ReservationState.waiting_date)
async def reservation_date_typed_fallback(message: Message):

    # The date step is now driven by the calendar buttons above; guide
    # anyone who types instead of tapping back to it, rather than
    # silently failing.
    await message.answer(
        "لطفاً یک تاریخ را از تقویم بالا با ضربه زدن روی عدد روز انتخاب کنید."
    )


@router.message(ReservationState.waiting_time)
async def reservation_get_time(message: Message, state: FSMContext, bot: Bot, db):

    text = (message.text or "").strip()

    if not TIME_PATTERN.match(text):
        await message.answer("❌ فرمت درست نیست. دوباره بفرستید (مثال: 18:30):")
        return

    data = await state.get_data()
    enrollment_id = data.get("enrollment_id")
    requested_date = data.get("requested_date")

    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)

    if not enrollment:
        await message.answer("❌ خطایی رخ داد.")
        await state.clear()
        return

    reservation = reservation_service.request_reservation(
        db=db,
        enrollment_id=enrollment_id,
        requested_date=requested_date,
        requested_time=text,
    )

    if reservation is None:
        await state.clear()
        await message.answer("⚠️ این زمان را قبلاً درخواست کرده‌اید و هنوز باز است.")
        return

    await state.clear()

    student = profile_service.get_profile_by_id(db, enrollment.user_id)

    await message.answer(
        "✅ درخواست رزرو شما ثبت شد و پس از تایید ادمین به شما اطلاع داده می‌شود."
    )

    await bot.send_message(
        chat_id=settings.OWNER_ID,
        text=f"""
📅 درخواست رزرو جدید

🎼 کلاس: {enrollment.online_course.name}
👤 هنرجو: {student.full_name if student else enrollment.user_id}
📆 تاریخ: {requested_date}
⏰ ساعت: {text}
""",
        reply_markup=reservation_review_keyboard(reservation.id),
    )


@router.message(ReservationState.waiting_receipt)
async def reservation_plan_receipt(message: Message, state: FSMContext, bot: Bot, db):
    proof = None
    if message.photo:
        proof = message.photo[-1].file_id
    elif message.document:
        proof = message.document.file_id
    if not proof:
        await message.answer("لطفاً عکس یا فایل رسید پرداخت را ارسال کنید.")
        return
    data = await state.get_data()
    reservation_ids = data.get("reservation_ids", [])
    submitted = []
    for reservation_id in reservation_ids:
        reservation = reservation_service.submit_payment(db, int(reservation_id), proof)
        if reservation:
            submitted.append(reservation.id)
    await state.clear()
    await message.answer(
        f"✅ رسید برای برنامه {len(submitted)} جلسه ثبت شد. پس از بررسی ادمین، رزروها نهایی می‌شوند."
    )
    if submitted:
        await bot.send_message(
            chat_id=settings.OWNER_ID,
            text=f"💳 رسید پرداخت برنامه آنلاین دریافت شد. رزروهای نیازمند بررسی: {', '.join(map(str, submitted))}",
            reply_markup=reservation_review_keyboard(submitted[0]),
        )
