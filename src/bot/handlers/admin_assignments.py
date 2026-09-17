from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.keyboards.assignment_keyboard import (
    admin_assignments_home_keyboard,
    admin_pending_submissions_keyboard,
    admin_submission_actions_keyboard,
)
from src.bot.states.assignment_states import AdminAssignmentState
from src.core.admin_access import is_admin_user
from src.core.constants import admin_actions
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.admin_log_service import AdminLogService
from src.services.assignment_service import AssignmentService, AssignmentServiceError
from src.services.online_course_service import OnlineCourseService
from src.services.profile_service import ProfileService

router = Router()
assignment_service = AssignmentService()
online_course_service = OnlineCourseService()
admin_log_service = AdminLogService()
profile_service = ProfileService()
telegram_repository = TelegramRepository()


@router.callback_query(F.data == "admin_assignments")
async def admin_assignments_home(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.message.edit_text(
        "📝 مدیریت تکالیف کلاس آنلاین:",
        reply_markup=admin_assignments_home_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_asg_pending")
async def admin_pending_list(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️", show_alert=True)
        return

    pending = assignment_service.list_pending_submissions(db)
    if not pending:
        await callback.message.edit_text(
            "✅ ارسال در انتظاری نیست.",
            reply_markup=admin_back_button("admin_assignments"),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📥 ارسال‌های در انتظار ({len(pending)}):",
        reply_markup=admin_pending_submissions_keyboard(pending),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("asg_admin_view_"))
async def admin_view_submission(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️", show_alert=True)
        return

    submission_id = int(callback.data.replace("asg_admin_view_", ""))
    submission = assignment_service.get_submission(db, submission_id)
    if not submission:
        await callback.answer("پیدا نشد", show_alert=True)
        return

    user = profile_service.get_profile_by_id(db, submission.user_id)
    assignment = assignment_service.get_assignment(db, submission.assignment_id)
    title = assignment.title if assignment else "—"
    name = user.full_name if user else "—"

    await callback.message.edit_text(
        f"📥 ارسال #{submission.id}\n"
        f"تکلیف: {title}\n"
        f"هنرجو: {name}\n"
        f"وضعیت: {submission.status.value}\n\n"
        f"{submission.content}",
        reply_markup=admin_submission_actions_keyboard(submission.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("asg_review_"))
async def admin_review_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️", show_alert=True)
        return
    submission_id = int(callback.data.replace("asg_review_", ""))
    await state.set_state(AdminAssignmentState.waiting_review_feedback)
    await state.update_data(submission_id=submission_id, return_mode=False)
    await callback.message.answer(
        "بازخورد را بنویسید. برای ثبت نمره در خط اول بنویسید: نمره:85\nسپس متن بازخورد."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("asg_return_"))
async def admin_return_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️", show_alert=True)
        return
    submission_id = int(callback.data.replace("asg_return_", ""))
    await state.set_state(AdminAssignmentState.waiting_review_feedback)
    await state.update_data(submission_id=submission_id, return_mode=True)
    await callback.message.answer("دلیل بازگشت برای اصلاح را بنویسید:")
    await callback.answer()


@router.message(AdminAssignmentState.waiting_review_feedback)
async def admin_review_submit(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return

    text = (message.text or "").strip()
    if text in {"/cancel", "انصراف"}:
        await state.clear()
        await message.answer("لغو شد.", reply_markup=admin_back_button("admin_assignments"))
        return

    data = await state.get_data()
    submission_id = data.get("submission_id")
    return_mode = bool(data.get("return_mode"))
    await state.clear()

    score = None
    feedback = text
    if text.startswith("نمره:"):
        first, _, rest = text.partition("\n")
        raw_score = first.replace("نمره:", "").strip()
        if raw_score.isdigit():
            score = int(raw_score)
            feedback = rest.strip() or text

    try:
        submission = assignment_service.review(
            db,
            submission_id,
            feedback=feedback,
            score=score,
            returned=return_mode,
        )
    except AssignmentServiceError as exc:
        mapping = {
            "not_found": "❌ پیدا نشد.",
            "already_reviewed": "❌ قبلاً بررسی شده.",
            "empty_feedback": "❌ بازخورد خالی است.",
            "invalid_score": "❌ نمره باید بین 0 تا 100 باشد.",
        }
        await message.answer(mapping.get(str(exc), "❌ خطا در بررسی."))
        return

    admin_log_service.log(
        db,
        message.from_user.id,
        admin_actions.ASSIGNMENT_REVIEW,
        f"بررسی ارسال تکلیف #{submission.id} ({submission.status.value})",
    )

    await message.answer(
        f"✅ ارسال #{submission.id} ثبت شد ({submission.status.value}).",
        reply_markup=admin_back_button("admin_assignments"),
    )

    try:
        tg = telegram_repository.get_by_user_id(db, submission.user_id)
        if tg:
            score_line = f"\nنمره: {submission.score}" if submission.score is not None else ""
            await message.bot.send_message(
                chat_id=int(tg.telegram_id),
                text=(
                    f"📝 نتیجه تکلیف #{submission.assignment_id}\n"
                    f"وضعیت: {submission.status.value}{score_line}\n\n"
                    f"{submission.admin_feedback}"
                ),
            )
    except Exception:
        await message.answer("⚠️ نتیجه ذخیره شد ولی ارسال به هنرجو ناموفق بود.")


@router.callback_query(F.data == "admin_asg_create")
async def admin_create_start(callback: CallbackQuery, state: FSMContext, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️", show_alert=True)
        return

    courses = online_course_service.get_active_courses(db)
    if not courses:
        await callback.message.answer("ابتدا حداقل یک کلاس آنلاین فعال بسازید.")
        await callback.answer()
        return

    lines = ["شناسه کلاس مورد نظر را بفرستید:"]
    for c in courses:
        lines.append(f"• {c.id}: {c.name}")

    await state.set_state(AdminAssignmentState.waiting_course_id)
    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.message(AdminAssignmentState.waiting_course_id)
async def admin_create_course_id(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("فقط عدد شناسه کلاس را بفرستید:")
        return

    course_id = int(raw)
    course = online_course_service.get_course_by_id(db, course_id)
    if not course:
        await message.answer("کلاس پیدا نشد. دوباره شناسه را بفرستید:")
        return

    await state.update_data(online_course_id=course_id)
    await state.set_state(AdminAssignmentState.waiting_title)
    await message.answer(f"عنوان تکلیف برای «{course.name}» را بفرستید:")


@router.message(AdminAssignmentState.waiting_title)
async def admin_create_title(message: Message, state: FSMContext):
    if not is_admin_user(message.from_user):
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("عنوان خالی است. دوباره بفرستید:")
        return
    await state.update_data(title=title)
    await state.set_state(AdminAssignmentState.waiting_description)
    await message.answer("توضیحات تکلیف را بفرستید:")


@router.message(AdminAssignmentState.waiting_description)
async def admin_create_description(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return

    description = (message.text or "").strip()
    data = await state.get_data()
    await state.clear()

    try:
        assignment = assignment_service.create_assignment(
            db,
            online_course_id=data["online_course_id"],
            title=data["title"],
            description=description,
        )
    except AssignmentServiceError as exc:
        await message.answer(f"❌ ثبت تکلیف ناموفق: {exc}")
        return

    admin_log_service.log(
        db,
        message.from_user.id,
        admin_actions.ASSIGNMENT_CREATE,
        f"تکلیف «{assignment.title}» برای کلاس {assignment.online_course_id} ساخته شد",
    )

    await message.answer(
        f"✅ تکلیف #{assignment.id} ثبت شد.",
        reply_markup=admin_back_button("admin_assignments"),
    )
