"""Admin online enrollment UX: student name buttons + session/fee management."""
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.profile_service import ProfileService
from src.services.online_course_service import OnlineCourseService
from src.bot.states.admin_states import AdminState
from src.bot.keyboards.admin_online_keyboard import (
    admin_student_picker_keyboard,
    payment_model_keyboard,
    admin_course_enrollments_keyboard,
    admin_enrollment_detail_keyboard,
)
from src.database.models.online_enrollment import EnrollmentStatus, PaymentModel
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.admin_log_service import AdminLogService
from src.core.constants import admin_actions
from src.core.config.settings import get_settings

router = Router()
online_enrollment_service = OnlineEnrollmentService()
profile_service = ProfileService()
online_course_service = OnlineCourseService()
telegram_repository = TelegramRepository()
admin_log_service = AdminLogService()
settings = get_settings()
PAGE_SIZE = 15


def _is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


def _detail(enrollment, student) -> str:
    plan = "ماهانه" if enrollment.payment_model.value == "monthly" else "ترمی"
    status_fa = {"active": "فعال", "paused": "متوقف", "ended": "پایان‌یافته"}.get(
        enrollment.status.value, enrollment.status.value
    )
    name = student.full_name if student else f"#{enrollment.user_id}"
    course_name = enrollment.online_course.name if enrollment.online_course else "—"
    notes = enrollment.admin_notes or "—"
    return (
        f"👤 {name}\n🎼 {course_name}\n📦 پلن: {plan}\n📊 وضعیت: {status_fa}\n"
        f"🎫 جلسات باقی‌مانده: {enrollment.remaining_sessions}\n"
        f"✅ جلسات برگزار شده: {enrollment.completed_sessions}\n📝 یادداشت: {notes}"
    )


@router.callback_query(F.data.startswith("admin_online_enroll_"))
async def enroll_start_picker(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    course_id = int(callback.data.replace("admin_online_enroll_", ""))
    students, total = profile_service.list_students(db, page=0, page_size=PAGE_SIZE)
    course = online_course_service.get_course_by_id(db, course_id)
    title = course.name if course else str(course_id)
    await callback.message.edit_text(
        f"🎼 {title}\n👤 هنرجو را انتخاب کنید:",
        reply_markup=admin_student_picker_keyboard(course_id, students, 0, total, PAGE_SIZE),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("aoep_"))
async def enroll_page(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    parts = callback.data.split("_")
    course_id, page = int(parts[1]), int(parts[2])
    students, total = profile_service.list_students(db, page=page, page_size=PAGE_SIZE)
    course = online_course_service.get_course_by_id(db, course_id)
    title = course.name if course else str(course_id)
    await callback.message.edit_text(
        f"🎼 {title}\n👤 صفحه {page + 1}:",
        reply_markup=admin_student_picker_keyboard(course_id, students, page, total, PAGE_SIZE),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("aoesearch_"))
async def enroll_search(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.update_data(online_course_id=int(callback.data.replace("aoesearch_", "")))
    await state.set_state(AdminState.waiting_student_phone)
    await callback.message.answer("🔎 شماره هنرجویی یا موبایل را بفرستید:")
    await callback.answer()


@router.callback_query(F.data.startswith("aoes_"))
async def enroll_select(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    parts = callback.data.split("_")
    course_id, user_id = int(parts[1]), int(parts[2])
    student = profile_service.get_profile_by_id(db, user_id)
    if not student:
        await callback.answer("هنرجو پیدا نشد", show_alert=True)
        return
    existing = online_enrollment_service.get_active_for_user_course(db, user_id, course_id)
    if existing:
        await callback.message.edit_text(
            f"ℹ️ «{student.full_name}» ثبت‌نام فعال دارد.\nجلسات: {existing.remaining_sessions}",
            reply_markup=admin_enrollment_detail_keyboard(existing),
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        f"نوع پرداخت «{student.full_name}» را انتخاب کنید:",
        reply_markup=payment_model_keyboard(user_id, course_id),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_oe_manage_pick")
async def manage_pick(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    courses = online_course_service.get_all_courses(db)
    rows = [[InlineKeyboardButton(text=f"🎼 {c.name}", callback_data=f"aom_{c.id}")] for c in courses]
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_online")])
    await callback.message.edit_text(
        "کلاس را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("aom_"))
async def manage_list(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    course_id = int(callback.data.replace("aom_", ""))
    enrollments = online_enrollment_service.get_by_course(db, course_id)
    course = online_course_service.get_course_by_id(db, course_id)
    profiles = {e.user_id: profile_service.get_profile_by_id(db, e.user_id) for e in enrollments}
    title = course.name if course else str(course_id)
    await callback.message.edit_text(
        f"🎼 {title}\nثبت‌نام‌ها ({len(enrollments)}):",
        reply_markup=admin_course_enrollments_keyboard(course_id, enrollments, profiles),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("aoeview_"))
async def view_enr(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    enrollment = online_enrollment_service.get_by_id(db, int(callback.data.replace("aoeview_", "")))
    if not enrollment:
        await callback.answer("پیدا نشد", show_alert=True)
        return
    student = profile_service.get_profile_by_id(db, enrollment.user_id)
    await callback.message.edit_text(
        _detail(enrollment, student),
        reply_markup=admin_enrollment_detail_keyboard(enrollment),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("aoesess_"))
async def adj_sess(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    parts = callback.data.split("_")
    eid, delta = int(parts[1]), int(parts[2])
    enrollment = online_enrollment_service.get_by_id(db, eid)
    if not enrollment:
        await callback.answer("پیدا نشد", show_alert=True)
        return
    enrollment = online_enrollment_service.adjust_remaining_sessions(db, enrollment, delta)
    student = profile_service.get_profile_by_id(db, enrollment.user_id)
    await callback.message.edit_text(
        _detail(enrollment, student),
        reply_markup=admin_enrollment_detail_keyboard(enrollment),
    )
    await callback.answer(f"جلسات: {enrollment.remaining_sessions}")


@router.callback_query(F.data.startswith("aoeset_"))
async def set_sess_start(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.update_data(edit_enrollment_id=int(callback.data.replace("aoeset_", "")))
    await state.set_state(AdminState.waiting_enrollment_sessions)
    await callback.message.answer("تعداد جلسات باقی‌مانده را عدد بفرستید:")
    await callback.answer()


@router.message(AdminState.waiting_enrollment_sessions)
async def set_sess_finish(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("❌ فقط عدد:")
        return
    data = await state.get_data()
    await state.clear()
    enrollment = online_enrollment_service.get_by_id(db, data["edit_enrollment_id"])
    if not enrollment:
        await message.answer("پیدا نشد.")
        return
    enrollment = online_enrollment_service.set_remaining_sessions(db, enrollment, int(raw))
    student = profile_service.get_profile_by_id(db, enrollment.user_id)
    await message.answer(_detail(enrollment, student), reply_markup=admin_enrollment_detail_keyboard(enrollment))


@router.callback_query(F.data.startswith("aoefee_"))
async def fee_start(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.update_data(edit_enrollment_id=int(callback.data.replace("aoefee_", "")))
    await state.set_state(AdminState.waiting_enrollment_fee)
    await callback.message.answer("مبلغ (تومان) را عدد بفرستید:")
    await callback.answer()


@router.message(AdminState.waiting_enrollment_fee)
async def fee_finish(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip().replace(",", "")
    if not raw.isdigit():
        await message.answer("❌ فقط عدد:")
        return
    data = await state.get_data()
    await state.clear()
    enrollment = online_enrollment_service.get_by_id(db, data["edit_enrollment_id"])
    if not enrollment:
        await message.answer("پیدا نشد.")
        return
    inst = online_enrollment_service.set_custom_fee(db, enrollment, int(raw))
    student = profile_service.get_profile_by_id(db, enrollment.user_id)
    await message.answer(
        _detail(enrollment, student) + f"\n💰 مبلغ: {inst.amount:,} تومان",
        reply_markup=admin_enrollment_detail_keyboard(enrollment),
    )


@router.callback_query(F.data.startswith("aoenote_"))
async def note_start(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.update_data(edit_enrollment_id=int(callback.data.replace("aoenote_", "")))
    await state.set_state(AdminState.waiting_enrollment_note)
    await callback.message.answer("یادداشت را بفرستید (یا - برای پاک کردن):")
    await callback.answer()


@router.message(AdminState.waiting_enrollment_note)
async def note_finish(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    data = await state.get_data()
    await state.clear()
    enrollment = online_enrollment_service.get_by_id(db, data["edit_enrollment_id"])
    if not enrollment:
        await message.answer("پیدا نشد.")
        return
    enrollment = online_enrollment_service.set_admin_notes(db, enrollment, None if raw == "-" else raw)
    student = profile_service.get_profile_by_id(db, enrollment.user_id)
    await message.answer(_detail(enrollment, student), reply_markup=admin_enrollment_detail_keyboard(enrollment))


@router.callback_query(F.data.startswith("aoestatus_"))
async def set_status(callback: CallbackQuery, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    parts = callback.data.split("_")
    eid, status_raw = int(parts[1]), parts[2]
    mapping = {"active": EnrollmentStatus.ACTIVE, "paused": EnrollmentStatus.PAUSED, "ended": EnrollmentStatus.ENDED}
    status = mapping.get(status_raw)
    if not status:
        await callback.answer("نامعتبر", show_alert=True)
        return
    enrollment = online_enrollment_service.get_by_id(db, eid)
    if not enrollment:
        await callback.answer("پیدا نشد", show_alert=True)
        return
    enrollment = online_enrollment_service.set_status(db, enrollment, status)
    student = profile_service.get_profile_by_id(db, enrollment.user_id)
    await callback.message.edit_text(_detail(enrollment, student), reply_markup=admin_enrollment_detail_keyboard(enrollment))
    await callback.answer("ذخیره شد")


@router.callback_query(F.data.startswith("ocpay_ok_"))
async def purchase_ok(callback: CallbackQuery, bot: Bot, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    parts = callback.data.replace("ocpay_ok_", "").split("_")
    user_id, course_id, plan, amount = int(parts[0]), int(parts[1]), parts[2], int(parts[3])
    course = online_course_service.get_course_by_id(db, course_id)
    if not course:
        await callback.answer("کلاس پیدا نشد", show_alert=True)
        return
    if online_enrollment_service.get_active_for_user_course(db, user_id, course_id):
        await callback.answer("ثبت‌نام فعال از قبل هست.", show_alert=True)
        return
    payment_model = PaymentModel.MONTHLY if plan == "monthly" else PaymentModel.TERM
    enrollment = online_enrollment_service.create_enrollment(
        db=db, user_id=user_id, online_course=course, payment_model=payment_model,
        custom_amount=amount if payment_model == PaymentModel.MONTHLY else None,
    )
    tg = telegram_repository.get_by_user_id(db, user_id)
    admin_log_service.log(db, callback.from_user.id, admin_actions.ONLINE_PURCHASE_APPROVE, f"online enroll {user_id}")
    if tg:
        await bot.send_message(
            chat_id=tg.telegram_id,
            text=f"✅ پرداخت تایید شد. در «{course.name}» ثبت‌نام شدید (جلسات: {enrollment.remaining_sessions}).",
        )
    base = callback.message.caption or callback.message.text or ""
    try:
        await callback.message.edit_text(base + "\n\n✅ تایید و ثبت‌نام شد.")
    except Exception:
        pass
    await callback.answer("انجام شد")


@router.callback_query(F.data.startswith("ocpay_no_"))
async def purchase_no(callback: CallbackQuery, bot: Bot, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    user_id = int(callback.data.replace("ocpay_no_", "").split("_")[0])
    tg = telegram_repository.get_by_user_id(db, user_id)
    admin_log_service.log(db, callback.from_user.id, admin_actions.ONLINE_PURCHASE_REJECT, f"reject {user_id}")
    if tg:
        await bot.send_message(chat_id=tg.telegram_id, text="❌ درخواست ثبت‌نام کلاس آنلاین تایید نشد.")
    base = callback.message.caption or callback.message.text or ""
    try:
        await callback.message.edit_text(base + "\n\n❌ رد شد.")
    except Exception:
        pass
    await callback.answer("رد شد")
