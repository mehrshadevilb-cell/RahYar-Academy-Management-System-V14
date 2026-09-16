"""Admin online implementation: reservations, attendance, course CRUD, slots.

Student enrollment primary handlers live in admin_online_enrollment.py
(registered first). This module owns reservation confirm/reject, attendance,
course catalog, weekly slots, and related admin actions.
"""
from __future__ import annotations

import re
import logging

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.keyboards.admin_online_keyboard import (
    admin_online_courses_keyboard,
    admin_online_manage_list_keyboard,
    admin_online_course_detail_keyboard,
)
from src.bot.keyboards.reservation_review_keyboard import reservation_review_keyboard
from src.bot.states.admin_states import AdminState
from src.core.config.settings import get_settings
from src.core.constants import admin_actions
from src.database.models.attendance import AttendanceStatus
from src.database.models.reservation import ReservationStatus
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.admin_log_service import AdminLogService
from src.services.attendance_service import AttendanceService
from src.services.online_course_service import OnlineCourseService
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.online_schedule_service import OnlineScheduleService
from src.services.profile_service import ProfileService
from src.services.reservation_service import ReservationService

logger = logging.getLogger(__name__)
router = Router()

reservation_service = ReservationService()
online_enrollment_service = OnlineEnrollmentService()
attendance_service = AttendanceService()
profile_service = ProfileService()
online_course_service = OnlineCourseService()
online_schedule_service = OnlineScheduleService()
telegram_repository = TelegramRepository()
admin_log_service = AdminLogService()
settings = get_settings()

SLOT_INPUT = re.compile(
    r"^(شنبه|یکشنبه|دوشنبه|سه‌شنبه|سه شنبه|چهارشنبه|پنجشنبه|جمعه)\s+(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})$"
)
SLOT_DAYS = {
    "دوشنبه": 0, "سه‌شنبه": 1, "سه شنبه": 1, "چهارشنبه": 2,
    "پنجشنبه": 3, "جمعه": 4, "شنبه": 5, "یکشنبه": 6,
}


def _is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


def _render_course_detail(course) -> str:
    return (
        f"🎓 {course.name}\n"
        f"مدرس: {course.teacher or '—'}\n"
        f"مدت هر جلسه: {course.duration_minutes} دقیقه\n"
        f"ماهانه: {course.monthly_price or 0:,} تومان ({course.monthly_sessions} جلسه)\n"
        f"ترم: {course.term_price or 0:,} تومان ({course.term_sessions} جلسه)\n"
        f"وضعیت: {'فعال' if course.is_active else 'غیرفعال'}"
    )


@router.callback_query(F.data == "admin_online")
async def admin_online_menu(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    courses = online_course_service.get_all_courses(db)
    await callback.message.edit_text(
        "🎓 مدیریت کلاس‌های آنلاین\n\nیک کلاس را انتخاب کنید یا کلاس جدید بسازید.",
        reply_markup=admin_online_courses_keyboard(courses),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_reservations")
async def admin_reservations(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    pending = reservation_service.get_pending(db)
    if not pending:
        await callback.message.edit_text(
            "✅ رزرو معلقی وجود ندارد.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="◀️ بازگشت", callback_data="admin_online")]]
            ),
        )
        await callback.answer()
        return

    lines = ["📋 رزروهای در انتظار تأیید:\n"]
    for r in pending[:20]:
        enrollment = online_enrollment_service.get_by_id(db, r.enrollment_id)
        course_name = enrollment.online_course.name if enrollment and enrollment.online_course else "?"
        student = profile_service.get_profile_by_id(db, enrollment.user_id) if enrollment else None
        student_name = (
            student.full_name if student and getattr(student, "full_name", None)
            else f"user#{enrollment.user_id if enrollment else '?'}"
        )
        status_label = r.status.value if hasattr(r.status, "value") else str(r.status)
        lines.append(
            f"#{r.id} | {student_name} | {course_name}\n"
            f"   {r.requested_date} ساعت {r.requested_time} | {status_label}"
        )
    await callback.message.edit_text("\n".join(lines)[:3500])
    for r in pending[:10]:
        try:
            await callback.message.answer(
                f"رزرو #{r.id}",
                reply_markup=reservation_review_keyboard(r.id),
            )
        except Exception:
            logger.exception("Failed reservation review keyboard for %s", r.id)
    await callback.answer()


@router.callback_query(F.data.startswith("res_confirm_") | F.data.startswith("res_payment_confirm_"))
async def confirm_reservation(callback: CallbackQuery, bot: Bot, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    reservation_id = int(callback.data.rsplit("_", 1)[-1])
    reservation = reservation_service.confirm(db, reservation_id)
    if not reservation:
        await callback.answer("رزرو پیدا نشد", show_alert=True)
        return
    if reservation.status != ReservationStatus.CONFIRMED:
        await callback.answer(
            "⚠️ ابتدا باید رسید پرداخت ثبت شده باشد.",
            show_alert=True,
        )
        return
    enrollment = online_enrollment_service.get_by_id(db, reservation.enrollment_id)
    try:
        admin_log_service.log(
            db, callback.from_user.id, admin_actions.RESERVATION_CONFIRM,
            f"رزرو #{reservation.id} تأیید شد",
        )
    except Exception:
        logger.exception("admin log")
    await callback.message.edit_text(
        f"✅ رزرو #{reservation.id} تأیید شد.\n"
        f"تاریخ: {reservation.requested_date} ساعت {reservation.requested_time}"
    )
    if enrollment:
        tg = telegram_repository.get_by_user_id(db, enrollment.user_id)
        if tg:
            try:
                await bot.send_message(
                    int(tg.telegram_id),
                    f"✅ رزرو کلاس شما تأیید شد.\n"
                    f"تاریخ: {reservation.requested_date}\n"
                    f"ساعت: {reservation.requested_time}",
                )
            except Exception:
                logger.exception("notify student")
    await callback.answer("تأیید شد")


@router.callback_query(F.data.startswith("res_reject_") | F.data.startswith("res_payment_reject_"))
async def reject_reservation(callback: CallbackQuery, bot: Bot, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    reservation_id = int(callback.data.rsplit("_", 1)[-1])
    reservation = reservation_service.reject(db, reservation_id, notes="rejected_by_admin")
    if not reservation:
        await callback.answer("رزرو پیدا نشد", show_alert=True)
        return
    try:
        admin_log_service.log(
            db, callback.from_user.id, admin_actions.RESERVATION_REJECT,
            f"رزرو #{reservation.id} رد شد",
        )
    except Exception:
        logger.exception("admin log")
    await callback.message.edit_text(f"❌ رزرو #{reservation.id} رد شد.")
    enrollment = online_enrollment_service.get_by_id(db, reservation.enrollment_id)
    if enrollment:
        tg = telegram_repository.get_by_user_id(db, enrollment.user_id)
        if tg:
            try:
                await bot.send_message(
                    int(tg.telegram_id),
                    f"❌ متأسفانه رزرو کلاس شما برای {reservation.requested_date} "
                    f"ساعت {reservation.requested_time} تأیید نشد.",
                )
            except Exception:
                logger.exception("notify reject")
    await callback.answer("رد شد")


async def _handle_attendance(callback: CallbackQuery, bot: Bot, db, status: AttendanceStatus):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    reservation_id = int(callback.data.rsplit("_", 1)[-1])
    reservation = reservation_service.get_by_id(db, reservation_id)
    if not reservation:
        await callback.answer("رزرو پیدا نشد", show_alert=True)
        return
    attendance_service.mark(
        db,
        reservation_id=reservation.id,
        enrollment_id=reservation.enrollment_id,
        status=status,
    )
    labels = {
        AttendanceStatus.PRESENT: "حاضر",
        AttendanceStatus.ABSENT: "غایب",
        AttendanceStatus.CANCELLED: "لغو (بدون کسر جلسه)",
    }
    label = labels.get(status, str(status))
    await callback.message.edit_text(f"✅ حضور: {label} (رزرو #{reservation.id})")
    enrollment = online_enrollment_service.get_by_id(db, reservation.enrollment_id)
    if enrollment and status == AttendanceStatus.PRESENT:
        online_enrollment_service.adjust_remaining_sessions(db, enrollment, -1)
    await callback.answer(label)


@router.callback_query(F.data.startswith("att_present_"))
async def attendance_present(callback: CallbackQuery, bot: Bot, db):
    await _handle_attendance(callback, bot, db, AttendanceStatus.PRESENT)


@router.callback_query(F.data.startswith("att_absent_"))
async def attendance_absent(callback: CallbackQuery, bot: Bot, db):
    await _handle_attendance(callback, bot, db, AttendanceStatus.ABSENT)


@router.callback_query(F.data.startswith("att_cancelled_"))
async def attendance_cancelled(callback: CallbackQuery, bot: Bot, db):
    await _handle_attendance(callback, bot, db, AttendanceStatus.CANCELLED)


@router.callback_query(F.data.startswith("admin_oc_slot_"))
async def admin_online_slot_start(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    course_id = int(callback.data.replace("admin_oc_slot_", ""))
    await state.update_data(online_slot_course_id=course_id)
    await state.set_state(AdminState.waiting_online_slot)
    await callback.message.answer(
        "🕒 زمان هفتگی را ارسال کنید؛ هر خط یک زمان.\n"
        "فرمت: شنبه 15:00-15:30\n"
        "برای پایان، /done را بفرستید."
    )
    await callback.answer()


@router.message(AdminState.waiting_online_slot)
async def admin_online_slot_add(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    text = (message.text or "").strip()
    if text == "/done":
        await state.clear()
        await message.answer("✅ ثبت زمان‌ها تمام شد.")
        return
    data = await state.get_data()
    course_id = data.get("online_slot_course_id")
    if not course_id:
        await state.clear()
        await message.answer("نشست منقضی شد. دوباره از منوی کلاس شروع کنید.")
        return
    added = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = SLOT_INPUT.match(line)
        if not m:
            await message.answer(f"❌ فرمت نامعتبر: {line}")
            continue
        day_name, start, end = m.group(1), m.group(2), m.group(3)
        weekday = SLOT_DAYS.get(day_name)
        if weekday is None:
            await message.answer(f"❌ روز نامعتبر: {day_name}")
            continue
        try:
            online_schedule_service.add_slot(db, course_id, weekday, start, end)
            added += 1
        except Exception as exc:
            await message.answer(f"❌ خطا برای {line}: {exc}")
    if added:
        await message.answer(f"✅ {added} زمان ثبت شد. خط بعدی یا /done")


@router.callback_query(F.data == "admin_online_manage")
async def admin_online_manage(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    courses = online_course_service.get_all_courses(db)
    await callback.message.edit_text(
        "🛠 مدیریت کلاس‌های آنلاین",
        reply_markup=admin_online_manage_list_keyboard(courses),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_oc_view_"))
async def admin_online_course_view(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    course_id = int(callback.data.replace("admin_oc_view_", ""))
    course = online_course_service.get_course_by_id(db, course_id)
    if not course:
        await callback.answer("کلاس پیدا نشد", show_alert=True)
        return
    await callback.message.edit_text(
        _render_course_detail(course),
        reply_markup=admin_online_course_detail_keyboard(course),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_oc_new")
async def admin_online_course_new(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_online_course_name)
    await callback.message.answer("نام کلاس آنلاین را بفرستید:")
    await callback.answer()


@router.message(AdminState.waiting_online_course_name)
async def admin_oc_name(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.update_data(name=(message.text or "").strip()[:120])
    await state.set_state(AdminState.waiting_online_course_teacher)
    await message.answer("نام مدرس (یا - برای خالی):")


@router.message(AdminState.waiting_online_course_teacher)
async def admin_oc_teacher(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    await state.update_data(teacher=None if raw in {"-", "—", ""} else raw[:120])
    await state.set_state(AdminState.waiting_online_course_duration)
    await message.answer("مدت هر جلسه به دقیقه (مثلاً 60):")


@router.message(AdminState.waiting_online_course_duration)
async def admin_oc_duration(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("❌ عدد معتبر بفرستید:")
        return
    await state.update_data(duration_minutes=int(raw))
    await state.set_state(AdminState.waiting_online_course_monthly_price)
    await message.answer("قیمت ماهانه (تومان، یا 0):")


@router.message(AdminState.waiting_online_course_monthly_price)
async def admin_oc_monthly_price(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip().replace(",", "")
    if not raw.isdigit():
        await message.answer("❌ عدد معتبر بفرستید:")
        return
    await state.update_data(monthly_price=int(raw))
    await state.set_state(AdminState.waiting_online_course_term_price)
    await message.answer("قیمت ترم (تومان، یا 0):")


@router.message(AdminState.waiting_online_course_term_price)
async def admin_oc_term_price(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip().replace(",", "")
    if not raw.isdigit():
        await message.answer("❌ عدد معتبر بفرستید:")
        return
    await state.update_data(term_price=int(raw))
    await state.set_state(AdminState.waiting_online_course_monthly_sessions)
    await message.answer("تعداد جلسات ماهانه:")


@router.message(AdminState.waiting_online_course_monthly_sessions)
async def admin_oc_monthly_sessions(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ عدد معتبر بفرستید:")
        return
    await state.update_data(monthly_sessions=int(raw))
    await state.set_state(AdminState.waiting_online_course_term_sessions)
    await message.answer("تعداد جلسات ترم:")


@router.message(AdminState.waiting_online_course_term_sessions)
async def admin_oc_term_sessions(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ عدد معتبر بفرستید:")
        return
    data = await state.get_data()
    await state.clear()
    course = online_course_service.create_course(
        db,
        name=data["name"],
        teacher=data.get("teacher"),
        duration_minutes=data["duration_minutes"],
        monthly_price=data.get("monthly_price"),
        term_price=data.get("term_price"),
        monthly_sessions=data["monthly_sessions"],
        term_sessions=int(raw),
    )
    try:
        admin_log_service.log(
            db, message.from_user.id, admin_actions.ONLINE_COURSE_CREATE,
            f"کلاس آنلاین «{course.name}» ساخته شد",
        )
    except Exception:
        logger.exception("admin log failed")
    await message.answer(
        f"✅ کلاس «{course.name}» ساخته شد.\n{_render_course_detail(course)}",
        reply_markup=admin_online_course_detail_keyboard(course),
    )


@router.callback_query(F.data.startswith("admin_oc_toggle_"))
async def admin_oc_toggle(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    course_id = int(callback.data.replace("admin_oc_toggle_", ""))
    course = online_course_service.toggle_active(db, course_id)
    if not course:
        await callback.answer("کلاس پیدا نشد", show_alert=True)
        return
    await callback.message.edit_text(
        _render_course_detail(course),
        reply_markup=admin_online_course_detail_keyboard(course),
    )
    await callback.answer("به‌روز شد")
