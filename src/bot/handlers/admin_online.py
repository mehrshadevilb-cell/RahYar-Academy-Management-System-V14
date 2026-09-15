import re

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.attendance_keyboard import attendance_keyboard

from src.services.reservation_service import ReservationService
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.attendance_service import AttendanceService
from src.services.profile_service import ProfileService
from src.services.online_course_service import OnlineCourseService
from src.services.online_schedule_service import OnlineScheduleService
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
online_schedule_service = OnlineScheduleService()
telegram_repository = TelegramRepository()
admin_log_service = AdminLogService()

settings = get_settings()
SLOT_INPUT = re.compile(r"^(شنبه|یکشنبه|دوشنبه|سه‌شنبه|سه شنبه|چهارشنبه|پنجشنبه|جمعه)\s+(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})$")
SLOT_DAYS = {"دوشنبه": 0, "سه‌شنبه": 1, "سه شنبه": 1, "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4, "شنبه": 5, "یکشنبه": 6}


def _is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


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
        await message.answer("✅ تنظیم زمان‌ها تمام شد.")
        return
    match = SLOT_INPUT.match(text)
    if not match:
        await message.answer("❌ فرمت نادرست. نمونه: شنبه 15:00-15:30")
        return
    day, start, end = match.groups()
    try:
        data = await state.get_data()
        slot = online_schedule_service.add_slot(db, data["online_slot_course_id"], SLOT_DAYS[day], start, end)
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
        return
    await message.answer(f"✅ زمان «{slot.label}» اضافه شد. زمان بعدی یا /done را بفرستید.")


@router.callback_query(F.data.startswith("res_confirm_") | F.data.startswith("res_payment_confirm_"))
async def confirm_reservation(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    reservation_id = int(callback.data.replace("res_confirm_", "").replace("res_payment_confirm_", ""))

    existing = reservation_service.get_by_id(db, reservation_id)

    if not existing:
        await callback.answer("درخواست پیدا نشد", show_alert=True)
        return
    if existing.status.value not in {"pending", "payment_submitted"}:
        await callback.answer("این درخواست قبلاً بررسی شده است.", show_alert=True)
        return

    reservation = reservation_service.confirm(db, reservation_id)

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

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ تایید شد.\nپس از برگزاری کلاس، وضعیت را ثبت کنید:",
        reply_markup=attendance_keyboard(reservation.id),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("res_reject_") | F.data.startswith("res_payment_reject_"))
async def reject_reservation(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    reservation_id = int(callback.data.replace("res_reject_", "").replace("res_payment_reject_", ""))

    existing = reservation_service.get_by_id(db, reservation_id)

    if not existing:
        await callback.answer("درخواست پیدا نشد", show_alert=True)
        return
    if existing.status.value not in {"pending", "payment_submitted"}:
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

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ رد شد."
    )

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

    await callback.message.edit_text(
        callback.message.text + f"\n\n{label}"
    )

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

@router.callback_query(F.data == "admin_online")
async def admin_online_menu(callback: CallbackQuery, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    courses = online_course_service.get_active_courses(db)

    if not courses:
        await callback.answer("هیچ کلاس آنلاینی ثبت نشده است.", show_alert=True)
        return

    await callback.message.edit_text(
        "🎼 برای ثبت‌نام هنرجو، کلاس مورد نظر را انتخاب کنید:",
        reply_markup=admin_online_courses_keyboard(courses),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("admin_online_enroll_"))
async def admin_online_enroll_start(
    callback: CallbackQuery, state: FSMContext
):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    course_id = int(callback.data.replace("admin_online_enroll_", ""))

    await state.update_data(online_course_id=course_id)
    await state.set_state(AdminState.waiting_student_phone)

    await callback.message.answer(
        "شماره هنرجویی یا شماره تماس هنرجو را بفرستید.\n"
        "شماره هنرجویی در پیام /start با قالب RH000123 نمایش داده می‌شود "
        "و هنرجو باید قبلاً /start را زده باشد:"
    )

    await callback.answer()


@router.message(AdminState.waiting_student_phone)
async def admin_online_enroll_phone(
    message: Message, state: FSMContext, db
):

    if not _is_owner(message.from_user.id):
        return

    identifier = (message.text or "").strip()
    normalized = identifier.upper().replace(" ", "")

    # Phone numbers remain supported.  RH000123 (or a bare numeric id) is the
    # stable student number shown to the student after /start.
    if normalized.startswith("RH") or (normalized.isdigit() and not normalized.startswith("09")):
        student = profile_service.get_profile_by_student_number(db, normalized)
    else:
        student = profile_service.get_profile_by_phone(db, identifier)

    if not student:
        await message.answer(
            "❌ هنرجویی با این شماره پیدا نشد. شماره هنرجویی را از پیام /start "
            "یا شماره موبایلی که ثبت کرده است ارسال کنید:"
        )
        return

    data = await state.get_data()
    course_id = data.get("online_course_id")

    await state.clear()

    await message.answer(
        f"نوع پرداخت «{student.full_name}» برای این کلاس را انتخاب کنید:",
        reply_markup=payment_model_keyboard(student.id, course_id),
    )


@router.callback_query(F.data.startswith("admin_online_plan_"))
async def admin_online_enroll_finish(
    callback: CallbackQuery, bot: Bot, db
):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    parts = callback.data.replace("admin_online_plan_", "").split("_")
    user_id, course_id, plan = int(parts[0]), int(parts[1]), parts[2]

    course = online_course_service.get_course_by_id(db, course_id)

    if not course:
        await callback.answer("کلاس پیدا نشد", show_alert=True)
        return

    payment_model = (
        PaymentModel.MONTHLY if plan == "monthly" else PaymentModel.TERM
    )

    enrollment = online_enrollment_service.create_enrollment(
        db=db,
        user_id=user_id,
        online_course=course,
        payment_model=payment_model,
    )

    student = profile_service.get_profile_by_id(db, user_id)
    telegram_account = telegram_repository.get_by_user_id(db, user_id)

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.ONLINE_ENROLLMENT_CREATE,
        f"«{student.full_name if student else user_id}» در کلاس «{course.name}» "
        f"با پرداخت {'ماهانه' if payment_model == PaymentModel.MONTHLY else 'ترمی'} ثبت‌نام شد",
    )

    if telegram_account:

        plan_fa = "ماهانه" if payment_model == PaymentModel.MONTHLY else "ترمی"

        await bot.send_message(
            chat_id=telegram_account.telegram_id,
            text=(
                f"🎼 شما در کلاس «{course.name}» با پرداخت {plan_fa} "
                f"ثبت‌نام شدید. برای رزرو جلسه از منوی «کلاس آنلاین» اقدام کنید."
            ),
        )

    await callback.message.edit_text(
        f"✅ «{student.full_name if student else user_id}» با موفقیت "
        f"در «{course.name}» ثبت‌نام شد."
    )

    await callback.answer()


@router.callback_query(F.data == "admin_reservations")
async def admin_reservations(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    pending = reservation_service.get_pending(db)
    if not pending:
        await callback.message.edit_text(
            "✅ هیچ درخواست رزروی در انتظار تایید نیست.",
            reply_markup=admin_back_button(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(f"📅 {len(pending)} درخواست رزرو در انتظار بررسی:")
    for reservation in pending:
        enrollment = online_enrollment_service.get_by_id(db, reservation.enrollment_id)
        student = profile_service.get_profile_by_id(db, enrollment.user_id) if enrollment else None
        course = online_course_service.get_course_by_id(db, enrollment.online_course_id) if enrollment else None
        text = (
            f"📅 رزرو #{reservation.id}\n"
            f"👤 {student.full_name if student else 'نامشخص'}\n"
            f"🎼 {course.name if course else 'نامشخص'}\n"
            f"📆 {reservation.requested_date}\n"
            f"⏰ {reservation.requested_time}"
        )
        from src.bot.keyboards.reservation_review_keyboard import reservation_review_keyboard
        await callback.message.answer(text, reply_markup=reservation_review_keyboard(reservation.id))

    await callback.answer()


# ---------------- Online course CRUD (admin management) ----------------

FIELD_LABELS_FA = {
    "name": "نام",
    "teacher": "مدرس",
    "duration_minutes": "مدت جلسه (دقیقه)",
    "monthly_price": "قیمت ماهانه (تومان)",
    "term_price": "قیمت ترمی (تومان)",
    "monthly_sessions": "تعداد جلسات ماهانه",
    "term_sessions": "تعداد جلسات ترم",
}

NUMERIC_FIELDS = {
    "duration_minutes", "monthly_price", "term_price",
    "monthly_sessions", "term_sessions",
}


@router.callback_query(F.data == "admin_online_manage")
async def admin_online_manage_list(callback: CallbackQuery, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    courses = online_course_service.get_all_courses(db)

    await callback.message.edit_text(
        "⚙️ مدیریت کلاس‌های آنلاین:\n(✅ فعال / 🚫 غیرفعال)",
        reply_markup=admin_online_manage_list_keyboard(courses),
    )

    await callback.answer()


def _render_course_detail(course) -> str:
    monthly_price = f"{course.monthly_price:,}" if course.monthly_price else "—"
    term_price = f"{course.term_price:,}" if course.term_price else "—"

    return (
        f"🎼 {course.name}\n\n"
        f"👨‍🏫 مدرس: {course.teacher or '—'}\n"
        f"⏱ مدت جلسه: {course.duration_minutes} دقیقه\n"
        f"💰 قیمت ماهانه: {monthly_price} تومان ({course.monthly_sessions} جلسه)\n"
        f"💰 قیمت ترمی: {term_price} تومان ({course.term_sessions} جلسه)\n"
        f"وضعیت: {'✅ فعال' if course.is_active else '🚫 غیرفعال'}"
    )


@router.callback_query(F.data.startswith("admin_oc_view_"))
async def admin_online_course_view(callback: CallbackQuery, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
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


@router.callback_query(F.data.startswith("admin_oc_toggle_"))
async def admin_online_course_toggle(callback: CallbackQuery, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    course_id = int(callback.data.replace("admin_oc_toggle_", ""))
    course = online_course_service.toggle_active(db, course_id)

    if not course:
        await callback.answer("کلاس پیدا نشد", show_alert=True)
        return

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.ONLINE_COURSE_TOGGLE,
        f"وضعیت کلاس «{course.name}» تغییر کرد "
        f"({'فعال' if course.is_active else 'غیرفعال'})",
    )

    await callback.message.edit_text(
        _render_course_detail(course),
        reply_markup=admin_online_course_detail_keyboard(course),
    )

    await callback.answer("وضعیت تغییر کرد ✅")


@router.callback_query(F.data.startswith("admin_oc_edit_"))
async def admin_online_course_edit_start(callback: CallbackQuery, state: FSMContext, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    remainder = callback.data.replace("admin_oc_edit_", "")
    field, course_id_str = remainder.rsplit("_", 1)
    course_id = int(course_id_str)

    course = online_course_service.get_course_by_id(db, course_id)

    if not course or field not in FIELD_LABELS_FA:
        await callback.answer("کلاس یا فیلد پیدا نشد", show_alert=True)
        return

    await state.update_data(course_id=course_id, field=field)
    await state.set_state(AdminState.waiting_online_course_field_edit)

    hint = " (فقط عدد)" if field in NUMERIC_FIELDS else ""

    await callback.message.answer(
        f"مقدار جدید «{FIELD_LABELS_FA[field]}»{hint} را بفرستید:"
    )

    await callback.answer()


@router.message(AdminState.waiting_online_course_field_edit)
async def admin_online_course_edit_save(message: Message, state: FSMContext, db):

    if not _is_owner(message.from_user.id):
        return

    data = await state.get_data()
    course_id = data.get("course_id")
    field = data.get("field")

    raw = (message.text or "").strip()

    if field in NUMERIC_FIELDS:
        cleaned = raw.replace(",", "")
        if not cleaned.isdigit():
            await message.answer("❌ لطفاً فقط عدد بفرستید. دوباره امتحان کنید:")
            return
        value = cleaned
    else:
        if not raw:
            await message.answer("❌ مقدار نمی‌تواند خالی باشد. دوباره بفرستید:")
            return
        value = raw

    await state.clear()

    try:
        course = online_course_service.update_field(db, course_id, field, value)
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
        return

    if not course:
        await message.answer("❌ کلاس پیدا نشد.")
        return

    admin_log_service.log(
        db, message.from_user.id, admin_actions.ONLINE_COURSE_EDIT,
        f"«{FIELD_LABELS_FA[field]}» کلاس «{course.name}» به «{value}» تغییر کرد",
    )

    await message.answer(
        f"✅ «{FIELD_LABELS_FA[field]}» به‌روزرسانی شد.",
        reply_markup=admin_online_course_detail_keyboard(course),
    )
    await message.answer(_render_course_detail(course))


# ---------------- Online course CRUD: create new course ----------------

@router.callback_query(F.data == "admin_oc_new")
async def admin_online_course_new_start(callback: CallbackQuery, state: FSMContext):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await state.set_state(AdminState.waiting_online_course_name)

    await callback.message.answer("نام کلاس آنلاین جدید را بفرستید (مثلاً «تنظیم صدا»):")

    await callback.answer()


@router.message(AdminState.waiting_online_course_name)
async def admin_online_course_new_name(message: Message, state: FSMContext):

    if not _is_owner(message.from_user.id):
        return

    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ نام نمی‌تواند خالی باشد. دوباره بفرستید:")
        return

    await state.update_data(name=name)
    await state.set_state(AdminState.waiting_online_course_teacher)

    await message.answer("نام مدرس را بفرستید (یا برای رد کردن «-» بفرستید):")


@router.message(AdminState.waiting_online_course_teacher)
async def admin_online_course_new_teacher(message: Message, state: FSMContext):

    if not _is_owner(message.from_user.id):
        return

    raw = (message.text or "").strip()
    teacher = None if raw in ("", "-") else raw

    await state.update_data(teacher=teacher)
    await state.set_state(AdminState.waiting_online_course_duration)

    await message.answer("مدت هر جلسه به دقیقه را بفرستید (مثلاً 60):")


@router.message(AdminState.waiting_online_course_duration)
async def admin_online_course_new_duration(message: Message, state: FSMContext):

    if not _is_owner(message.from_user.id):
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ لطفاً فقط عدد بفرستید. دوباره امتحان کنید:")
        return

    await state.update_data(duration_minutes=int(raw))
    await state.set_state(AdminState.waiting_online_course_monthly_price)

    await message.answer("قیمت پلن ماهانه را به تومان بفرستید (یا «-» برای غیرفعال کردن این پلن):")


@router.message(AdminState.waiting_online_course_monthly_price)
async def admin_online_course_new_monthly_price(message: Message, state: FSMContext):

    if not _is_owner(message.from_user.id):
        return

    raw = (message.text or "").strip().replace(",", "")
    if raw == "-":
        monthly_price = None
    elif raw.isdigit():
        monthly_price = int(raw)
    else:
        await message.answer("❌ لطفاً فقط عدد یا «-» بفرستید. دوباره امتحان کنید:")
        return

    await state.update_data(monthly_price=monthly_price)
    await state.set_state(AdminState.waiting_online_course_term_price)

    await message.answer("قیمت پلن ترمی را به تومان بفرستید (یا «-» برای غیرفعال کردن این پلن):")


@router.message(AdminState.waiting_online_course_term_price)
async def admin_online_course_new_term_price(message: Message, state: FSMContext):

    if not _is_owner(message.from_user.id):
        return

    raw = (message.text or "").strip().replace(",", "")
    if raw == "-":
        term_price = None
    elif raw.isdigit():
        term_price = int(raw)
    else:
        await message.answer("❌ لطفاً فقط عدد یا «-» بفرستید. دوباره امتحان کنید:")
        return

    await state.update_data(term_price=term_price)
    await state.set_state(AdminState.waiting_online_course_monthly_sessions)

    await message.answer("تعداد جلسات هر دوره ماهانه را بفرستید (مثلاً 4):")


@router.message(AdminState.waiting_online_course_monthly_sessions)
async def admin_online_course_new_monthly_sessions(message: Message, state: FSMContext):

    if not _is_owner(message.from_user.id):
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ لطفاً فقط عدد بفرستید. دوباره امتحان کنید:")
        return

    await state.update_data(monthly_sessions=int(raw))
    await state.set_state(AdminState.waiting_online_course_term_sessions)

    await message.answer("تعداد جلسات هر دوره ترمی را بفرستید (مثلاً 12):")


@router.message(AdminState.waiting_online_course_term_sessions)
async def admin_online_course_new_term_sessions(message: Message, state: FSMContext, db):

    if not _is_owner(message.from_user.id):
        return

    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ لطفاً فقط عدد بفرستید. دوباره امتحان کنید:")
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

    admin_log_service.log(
        db, message.from_user.id, admin_actions.ONLINE_COURSE_CREATE,
        f"کلاس آنلاین «{course.name}» ساخته شد",
    )

    await message.answer(
        f"✅ کلاس «{course.name}» ساخته شد.",
        reply_markup=admin_online_course_detail_keyboard(course),
    )
    await message.answer(_render_course_detail(course))
