import re

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.bot.states.reservation_states import ReservationState
from src.bot.keyboards.reservation_review_keyboard import reservation_review_keyboard
from src.bot.keyboards.jalali_calendar_keyboard import jalali_calendar_keyboard
from src.bot.keyboards.class_slot_keyboard import student_open_slots_keyboard

from src.services.online_course_service import OnlineCourseService
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.reservation_service import ReservationService
from src.services.class_slot_service import ClassSlotService
from src.services.profile_service import ProfileService
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
class_slot_service = ClassSlotService()
profile_service = ProfileService()
telegram_repository = TelegramRepository()

settings = get_settings()

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _plan_fa(payment_model) -> str:
    value = payment_model.value if hasattr(payment_model, "value") else str(payment_model)
    return {"monthly": "ماهانه (۴ جلسه)", "term": "ترمی (۱۲ جلسه)"}.get(value, value)


def _enrollment_keyboard(enrollment_id: int, status_value: str):
    if status_value == "paused":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💳 برای ادامه باید قسط بعدی را پرداخت کنید",
                        callback_data="slot_paused_info",
                    )
                ]
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 درخواست رزرو کلاس",
                    callback_data=f"reserve_menu_{enrollment_id}",
                )
            ]
        ]
    )


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

        status_value = enrollment.status.value
        status_fa = {
            "active": "فعال",
            "paused": "متوقف (نیاز به پرداخت دوره بعد)",
            "ended": "پایان‌یافته",
        }.get(status_value, status_value)

        await message.answer(
            text=(
                f"🎼 {enrollment.online_course.name}\n\n"
                f"نوع پرداخت: {_plan_fa(enrollment.payment_model)}\n"
                f"وضعیت: {status_fa}\n"
                f"جلسات باقی‌مانده: {enrollment.remaining_sessions}\n"
                f"جلسات برگزار شده: {enrollment.completed_sessions}"
            ),
            reply_markup=_enrollment_keyboard(enrollment.id, status_value),
        )


@router.callback_query(F.data == "slot_paused_info")
async def slot_paused_info(callback: CallbackQuery):
    await callback.answer(
        "جلسات این دوره تمام شده است. پس از تایید پرداخت دوره بعد، دوباره می‌توانید رزرو کنید.",
        show_alert=True,
    )


@router.callback_query(F.data == "slot_cancel")
async def slot_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("لغو شد.")
    await callback.answer()


@router.callback_query(F.data.startswith("reserve_menu_"))
async def reservation_menu(callback: CallbackQuery, state: FSMContext, db):
    enrollment_id = int(callback.data.replace("reserve_menu_", ""))

    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))

    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return

    if enrollment.status.value != "active" or enrollment.remaining_sessions <= 0:
        await callback.answer("این کلاس دیگر جلسه قابل رزرو ندارد.", show_alert=True)
        return

    slots = class_slot_service.get_open_by_course(db, enrollment.online_course_id)

    if slots:
        await callback.message.answer(
            "🗓 از بین زمان‌های آزاد زیر یکی را انتخاب کنید، یا تاریخ دلخواه بزنید:",
            reply_markup=student_open_slots_keyboard(slots, enrollment_id),
        )
    else:
        await state.update_data(enrollment_id=enrollment_id)
        await state.set_state(ReservationState.waiting_date)
        jy, jm, _ = today_jalali()
        await callback.message.answer(
            "📅 تاریخ مورد نظر را از تقویم زیر انتخاب کنید:",
            reply_markup=jalali_calendar_keyboard(enrollment_id, jy, jm),
        )

    await callback.answer()


@router.callback_query(F.data.startswith("slot_pick_"))
async def slot_pick(callback: CallbackQuery, bot: Bot, db):
    parts = callback.data.replace("slot_pick_", "").split("_")
    if len(parts) != 2:
        await callback.answer("داده نامعتبر", show_alert=True)
        return

    enrollment_id, slot_id = int(parts[0]), int(parts[1])

    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))

    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return

    if enrollment.status.value != "active" or enrollment.remaining_sessions <= 0:
        await callback.answer("این کلاس دیگر جلسه قابل رزرو ندارد.", show_alert=True)
        return

    reservation = reservation_service.request_from_slot(db, enrollment_id, slot_id)

    if reservation is None:
        await callback.answer(
            "این زمان دیگر در دسترس نیست یا قبلاً درخواست داده‌اید.",
            show_alert=True,
        )
        return

    student = profile_service.get_profile_by_id(db, enrollment.user_id)

    await callback.message.edit_text(
        f"✅ درخواست رزرو شما برای {reservation.requested_date} ساعت {reservation.requested_time} ثبت شد.\n"
        "پس از تایید ادمین اطلاع داده می‌شود."
    )

    await bot.send_message(
        chat_id=settings.OWNER_ID,
        text=(
            f"📅 درخواست رزرو جدید (از لیست زمان آزاد)\n\n"
            f"🎼 کلاس: {enrollment.online_course.name}\n"
            f"👤 هنرجو: {student.full_name if student else enrollment.user_id}\n"
            f"📆 تاریخ: {reservation.requested_date}\n"
            f"⏰ ساعت: {reservation.requested_time}"
        ),
        reply_markup=reservation_review_keyboard(reservation.id),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("reserve_"))
async def reservation_start(callback: CallbackQuery, state: FSMContext, db):
    if callback.data.startswith("reserve_menu_"):
        return

    enrollment_id = int(callback.data.replace("reserve_", ""))

    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))

    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return

    if enrollment.status.value != "active" or enrollment.remaining_sessions <= 0:
        await callback.answer("این کلاس دیگر جلسه قابل رزرو ندارد.", show_alert=True)
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

    await state.update_data(requested_date=requested_date, enrollment_id=enrollment_id)
    await state.set_state(ReservationState.waiting_time)

    await callback.message.edit_text(
        f"📅 تاریخ انتخابی: {jd} {JALALI_MONTH_NAMES[jm - 1]} {jy}\n\n"
        "⏰ ساعت مورد نظر را به فرمت 18:30 ارسال کنید:"
    )

    await callback.answer()


@router.message(ReservationState.waiting_date)
async def reservation_date_typed_fallback(message: Message):
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
        text=(
            f"📅 درخواست رزرو جدید\n\n"
            f"🎼 کلاس: {enrollment.online_course.name}\n"
            f"👤 هنرجو: {student.full_name if student else enrollment.user_id}\n"
            f"📆 تاریخ: {requested_date}\n"
            f"⏰ ساعت: {text}"
        ),
        reply_markup=reservation_review_keyboard(reservation.id),
    )
