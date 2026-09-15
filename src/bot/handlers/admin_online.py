from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.attendance_keyboard import attendance_keyboard

from src.services.reservation_service import ReservationService
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.attendance_service import AttendanceService
from src.services.profile_service import ProfileService
from src.services.online_course_service import OnlineCourseService
from src.bot.states.admin_states import AdminState
from src.bot.keyboards.admin_online_keyboard import (
    admin_online_courses_keyboard,
    payment_model_keyboard,
    admin_online_manage_list_keyboard,
    admin_online_course_detail_keyboard,
)
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.database.models.online_enrollment import PaymentModel
from src.database.models.attendance import AttendanceStatus
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.admin_log_service import AdminLogService
from src.core.constants import admin_actions
from src.core.config.settings import get_settings


router = Router()

reservation_service = ReservationService()
online_enrollment_service = OnlineEnrollmentService()
attendance_service = AttendanceService()
profile_service = ProfileService()
online_course_service = OnlineCourseService()
telegram_repository = TelegramRepository()
admin_log_service = AdminLogService()

settings = get_settings()


def _is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


@router.callback_query(
    F.data.startswith("res_payment_confirm_") | F.data.startswith("res_confirm_")
)
async def confirm_reservation(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    raw = callback.data
    if raw.startswith("res_payment_confirm_"):
        reservation_id = int(raw.replace("res_payment_confirm_", ""))
    else:
        reservation_id = int(raw.replace("res_confirm_", ""))

    existing = reservation_service.get_by_id(db, reservation_id)

    if not existing:
        await callback.answer("درخواست پیدا نشد", show_alert=True)
        return

    # Payment gate: only receipt-submitted (or legacy pending) can be confirmed.
    allowed = {"payment_submitted", "pending"}
    if existing.status.value not in allowed:
        await callback.answer("این درخواست قبلاً بررسی شده است.", show_alert=True)
        return

    # Legacy PENDING rows never went through submit_payment; promote them so
    # the service-level gate accepts the confirm.
    if existing.status.value == "pending":
        reservation_service.submit_payment(
            db, existing.id, proof=existing.payment_proof or "legacy-pending"
        )

    reservation = reservation_service.confirm(db, reservation_id)

    if reservation is None or reservation.status.value != "confirmed":
        await callback.answer(
            "تایید ممکن نیست. ابتدا باید رسید پرداخت ثبت شده باشد.",
            show_alert=True,
        )
        return

    enrollment = online_enrollment_service.get_by_id(db, reservation.enrollment_id)

    telegram_account = telegram_repository.get_by_user_id(db, enrollment.user_id)

    if telegram_account:

        await bot.send_message(
            chat_id=telegram_account.telegram_id,
            text=(
                f"✅ رزرو کلاس شما تایید شد.\n"
                f"📆 {reservation.requested_date} - ⏰ {reservation.requested_time}"
            ),
        )

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.RESERVATION_CONFIRM,
        f"رزرو #{reservation.id} برای تاریخ {reservation.requested_date} تایید شد",
    )

    body = callback.message.caption or callback.message.text or ""
    try:
        if callback.message.caption is not None:
            await callback.message.edit_caption(
                caption=body + "\n\n✅ تایید شد.\nپس از برگزاری کلاس، وضعیت را ثبت کنید:",
                reply_markup=attendance_keyboard(reservation.id),
            )
        else:
            await callback.message.edit_text(
                body + "\n\n✅ تایید شد.\nپس از برگزاری کلاس، وضعیت را ثبت کنید:",
                reply_markup=attendance_keyboard(reservation.id),
            )
    except Exception:
        await callback.message.answer(
            body + "\n\n✅ تایید شد.\nپس از برگزاری کلاس، وضعیت را ثبت کنید:",
            reply_markup=attendance_keyboard(reservation.id),
        )

    await callback.answer()


@router.callback_query(
    F.data.startswith("res_payment_reject_") | F.data.startswith("res_reject_")
)
async def reject_reservation(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    raw = callback.data
    if raw.startswith("res_payment_reject_"):
        reservation_id = int(raw.replace("res_payment_reject_", ""))
    else:
        reservation_id = int(raw.replace("res_reject_", ""))

    existing = reservation_service.get_by_id(db, reservation_id)

    if not existing:
        await callback.answer("درخواست پیدا نشد", show_alert=True)
        return

    allowed = {"payment_submitted", "pending", "waiting_payment"}
    if existing.status.value not in allowed:
        await callback.answer("این درخواست قبلاً بررسی شده است.", show_alert=True)
        return

    reservation = reservation_service.reject(db, reservation_id)

    enrollment = online_enrollment_service.get_by_id(db, reservation.enrollment_id)

    telegram_account = telegram_repository.get_by_user_id(db, enrollment.user_id)

    if telegram_account:

        await bot.send_message(
            chat_id=telegram_account.telegram_id,
            text=(
                "❌ زمان درخواستی شما تایید نشد.\n"
                "لطفاً یک زمان دیگر رزرو کنید."
            ),
        )

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.RESERVATION_REJECT,
        f"رزرو #{reservation.id} برای تاریخ {reservation.requested_date} رد شد",
    )

    body = callback.message.caption or callback.message.text or ""
    try:
        if callback.message.caption is not None:
            await callback.message.edit_caption(caption=body + "\n\n❌ رد شد.")
        else:
            await callback.message.edit_text(body + "\n\n❌ رد شد.")
    except Exception:
        await callback.message.answer(body + "\n\n❌ رد شد.")

    await callback.answer()


async def _handle_attendance(
    callback: CallbackQuery,
    bot: Bot,
    db,
    reservation_id: int,
    status: AttendanceStatus,
    student_message: str,
    label: str,
):

    reservation = reservation_service.get_by_id(db, reservation_id)

    if not reservation:
        await callback.answer("درخواست پیدا نشد", show_alert=True)
        return

    enrollment = online_enrollment_service.get_by_id(db, reservation.enrollment_id)

    try:
        attendance_service.mark_attendance(
            db=db,
            enrollment=enrollment,
            session_date=reservation.requested_date,
            status=status,
            reservation_id=reservation.id,
        )
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.ATTENDANCE_MARK,
        f"وضعیت جلسه‌ی رزرو #{reservation.id} به «{label}» ثبت شد",
    )

    telegram_account = telegram_repository.get_by_user_id(db, enrollment.user_id)

    if telegram_account:

        await bot.send_message(
            chat_id=telegram_account.telegram_id,
            text=student_message,
        )

    body = callback.message.caption or callback.message.text or ""
    try:
        if callback.message.caption is not None:
            await callback.message.edit_caption(caption=body + f"\n\n{label}")
        else:
            await callback.message.edit_text(body + f"\n\n{label}")
    except Exception:
        await callback.message.answer(body + f"\n\n{label}")

    await callback.answer(label)


@router.callback_query(F.data.startswith("att_present_"))
async def attendance_present(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    reservation_id = int(callback.data.replace("att_present_", ""))

    await _handle_attendance(
        callback, bot, db, reservation_id,
        AttendanceStatus.PRESENT,
        "✅ حضور شما در کلاس ثبت شد.",
        "✅ حاضر ثبت شد.",
    )


@router.callback_query(F.data.startswith("att_absent_"))
async def attendance_absent(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    reservation_id = int(callback.data.replace("att_absent_", ""))

    await _handle_attendance(
        callback, bot, db, reservation_id,
        AttendanceStatus.ABSENT,
        "غیبت شما در این جلسه ثبت شد.",
        "❌ غایب ثبت شد.",
    )


@router.callback_query(F.data.startswith("att_cancelled_"))
async def attendance_cancelled(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    reservation_id = int(callback.data.replace("att_cancelled_", ""))

    await _handle_attendance(
        callback, bot, db, reservation_id,
        AttendanceStatus.CANCELLED,
        "این جلسه لغو شد و جزو جلسات شما حساب نمی‌شود.",
        "🚫 لغو ثبت شد (جلسه مصرف نشد).",
    )
