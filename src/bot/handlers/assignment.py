from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.assignment_keyboard import (
    student_assignment_detail_keyboard,
    student_assignments_keyboard,
)
from src.bot.states.assignment_states import StudentAssignmentState
from src.core.config.settings import get_settings
from src.services.assignment_service import AssignmentService, AssignmentServiceError
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.profile_service import ProfileService

router = Router()
assignment_service = AssignmentService()
enrollment_service = OnlineEnrollmentService()
profile_service = ProfileService()
settings = get_settings()


@router.message(F.text == "📝 تکالیف")
async def student_assignments_menu(message: Message, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    enrollments = enrollment_service.get_active_by_user(db, user.id)
    if not enrollments:
        await message.answer("شما در کلاس آنلاینی ثبت‌نام نیستید.")
        return

    seen_courses: set[int] = set()
    all_assignments = []
    for enrollment in enrollments:
        cid = enrollment.online_course_id
        if cid in seen_courses:
            continue
        seen_courses.add(cid)
        all_assignments.extend(assignment_service.list_for_course(db, cid, active_only=True))

    if not all_assignments:
        await message.answer("در حال حاضر تکلیف فعالی برای کلاس‌های شما ثبت نشده است.")
        return

    await message.answer(
        "📝 تکالیف فعال کلاس‌های شما:",
        reply_markup=student_assignments_keyboard(all_assignments),
    )


@router.callback_query(F.data.startswith("asg_view_"))
async def student_view_assignment(callback: CallbackQuery, db):
    assignment_id = int(callback.data.replace("asg_view_", ""))
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    assignment = assignment_service.get_assignment(db, assignment_id)

    if not user or not assignment or not assignment.is_active:
        await callback.answer("تکلیف در دسترس نیست", show_alert=True)
        return

    existing = assignment_service.get_user_submission(db, assignment_id, user.id)
    status_line = "هنوز ارسال نکرده‌اید"
    if existing:
        status_line = f"وضعیت ارسال: {existing.status.value}"
        if existing.admin_feedback:
            status_line += f"\nبازخورد: {existing.admin_feedback[:300]}"
        if existing.score is not None:
            status_line += f"\nنمره: {existing.score}"

    course_name = assignment.online_course.name if assignment.online_course else "—"

    await callback.message.answer(
        f"📝 {assignment.title}\n"
        f"🎼 کلاس: {course_name}\n\n"
        f"{assignment.description}\n\n"
        f"{status_line}",
        reply_markup=student_assignment_detail_keyboard(assignment.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("asg_submit_"))
async def student_submit_start(callback: CallbackQuery, state: FSMContext):
    assignment_id = int(callback.data.replace("asg_submit_", ""))
    await state.set_state(StudentAssignmentState.waiting_submission)
    await state.update_data(assignment_id=assignment_id)
    await callback.message.answer(
        "پاسخ تکلیف را به‌صورت متن بفرستید (لینک فایل/توضیح). برای انصراف «انصراف» را بفرستید:"
    )
    await callback.answer()


@router.message(StudentAssignmentState.waiting_submission)
async def student_submit_content(message: Message, state: FSMContext, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await state.clear()
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    text = (message.text or "").strip()
    if text in {"/cancel", "انصراف"}:
        await state.clear()
        await message.answer("✅ ارسال تکلیف لغو شد.")
        return

    data = await state.get_data()
    assignment_id = data.get("assignment_id")

    try:
        submission = assignment_service.submit(
            db,
            assignment_id=assignment_id,
            user_id=user.id,
            content=text,
        )
    except AssignmentServiceError as exc:
        mapping = {
            "assignment_unavailable": "❌ تکلیف در دسترس نیست.",
            "empty_content": "❌ پاسخ خالی است.",
            "content_too_long": "❌ پاسخ خیلی طولانی است.",
            "not_enrolled": "❌ شما در این کلاس ثبت‌نام فعال ندارید.",
            "already_pending": "❌ یک ارسال در انتظار بررسی دارید.",
        }
        await message.answer(mapping.get(str(exc), "❌ ثبت ارسال ناموفق بود."))
        if str(exc) != "empty_content":
            await state.clear()
        return

    await state.clear()
    await message.answer(f"✅ پاسخ تکلیف ثبت شد (#{submission.id}). پس از بررسی مطلع می‌شوید.")

    if settings.OWNER_ID:
        try:
            await message.bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    f"📥 ارسال تکلیف جدید #{submission.id}\n"
                    f"کاربر: {user.full_name} ({message.from_user.id})\n"
                    f"تکلیف: {submission.assignment_id}\n\n"
                    f"{submission.content[:1200]}"
                ),
            )
        except Exception:
            pass
