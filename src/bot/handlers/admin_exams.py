from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.keyboards.exam_keyboard import admin_exam_home_keyboard
from src.bot.states.exam_states import AdminExamState
from src.core.config.settings import get_settings
from src.core.constants import admin_actions
from src.services.admin_log_service import AdminLogService
from src.services.exam_service import ExamService, ExamServiceError
from src.services.online_course_service import OnlineCourseService

router = Router()
settings = get_settings()
exam_service = ExamService()
online_course_service = OnlineCourseService()
admin_log_service = AdminLogService()


def _is_owner(user_id: int) -> bool:
    return bool(settings.OWNER_ID) and user_id == settings.OWNER_ID


@router.callback_query(F.data == "admin_exams")
async def admin_exam_home(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.message.edit_text(
        "📋 مدیریت آزمون‌های رسمی:",
        reply_markup=admin_exam_home_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_exam_create")
async def admin_exam_create_start(callback: CallbackQuery, state: FSMContext, db):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    courses = online_course_service.get_active_courses(db)
    if not courses:
        await callback.message.answer("ابتدا یک کلاس آنلاین فعال بسازید.")
        await callback.answer()
        return
    lines = ["شناسه کلاس را بفرستید:"]
    for c in courses:
        lines.append(f"• {c.id}: {c.name}")
    await state.set_state(AdminExamState.waiting_course_id)
    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.message(AdminExamState.waiting_course_id)
async def admin_exam_course(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("فقط عدد:")
        return
    course = online_course_service.get_course_by_id(db, int(raw))
    if not course:
        await message.answer("کلاس پیدا نشد:")
        return
    await state.update_data(online_course_id=course.id)
    await state.set_state(AdminExamState.waiting_title)
    await message.answer(f"عنوان آزمون رسمی برای «{course.name}»:")


@router.message(AdminExamState.waiting_title)
async def admin_exam_title(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("عنوان خالی است:")
        return
    await state.update_data(title=title)
    await state.set_state(AdminExamState.waiting_pass_score)
    await message.answer("حد نصاب قبولی را به درصد بفرستید (مثلاً 70):")


@router.message(AdminExamState.waiting_pass_score)
async def admin_exam_pass_score(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (0 <= int(raw) <= 100):
        await message.answer("عدد بین ۰ تا ۱۰۰:")
        return
    await state.update_data(pass_score_percent=int(raw))
    await state.set_state(AdminExamState.waiting_max_attempts)
    await message.answer("حداکثر تعداد تلاش مجاز را بفرستید (مثلاً 1):")


@router.message(AdminExamState.waiting_max_attempts)
async def admin_exam_max_attempts(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) < 1:
        await message.answer("عدد صحیح بزرگ‌تر از صفر:")
        return
    data = await state.get_data()
    await state.clear()
    try:
        exam = exam_service.create_exam(
            db,
            online_course_id=data["online_course_id"],
            title=data["title"],
            pass_score_percent=data["pass_score_percent"],
            max_attempts=int(raw),
        )
    except ExamServiceError as exc:
        await message.answer(f"❌ {exc}")
        return

    admin_log_service.log(
        db,
        message.from_user.id,
        admin_actions.EXAM_CREATE,
        f"آزمون رسمی «{exam.title}» #{exam.id} ساخته شد",
    )
    await message.answer(
        f"✅ آزمون رسمی #{exam.id} ثبت شد.\n"
        f"حد نصاب: {exam.pass_score_percent}% | تلاش: {exam.max_attempts}",
        reply_markup=admin_back_button("admin_exams"),
    )


@router.callback_query(F.data == "admin_exam_add_q")
async def admin_exam_add_q_start(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminExamState.waiting_question_text)
    await callback.message.answer(
        "شناسه آزمون و متن سؤال را در دو خط بفرستید:\n"
        "مثال:\n2\nکدام گزینه درباره هارمونی درست است؟"
    )
    await callback.answer()


@router.message(AdminExamState.waiting_question_text)
async def admin_exam_q_text(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    text = (message.text or "").strip()
    lines = text.split("\n", 1)
    if len(lines) < 2 or not lines[0].strip().isdigit():
        await message.answer("فرمت: خط اول شناسه، خط دوم متن سؤال")
        return
    await state.update_data(exam_id=int(lines[0].strip()), question_text=lines[1].strip())
    await state.set_state(AdminExamState.waiting_options)
    await message.answer("گزینه‌ها را هر کدام در یک خط بفرستید (۲ تا ۶):")


@router.message(AdminExamState.waiting_options)
async def admin_exam_options(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    options = [ln.strip() for ln in (message.text or "").splitlines() if ln.strip()]
    if len(options) < 2:
        await message.answer("حداقل ۲ گزینه لازم است.")
        return
    await state.update_data(options=options)
    await state.set_state(AdminExamState.waiting_correct_index)
    numbered = "\n".join(f"{i}: {o}" for i, o in enumerate(options))
    await message.answer(f"شماره گزینه درست (از ۰):\n{numbered}")


@router.message(AdminExamState.waiting_correct_index)
async def admin_exam_correct(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("فقط عدد:")
        return
    data = await state.get_data()
    await state.clear()
    try:
        question = exam_service.add_question(
            db,
            exam_id=data["exam_id"],
            text=data["question_text"],
            options=data["options"],
            correct_index=int(raw),
        )
    except ExamServiceError as exc:
        await message.answer(f"❌ {exc}")
        return

    admin_log_service.log(
        db,
        message.from_user.id,
        admin_actions.EXAM_QUESTION_ADD,
        f"سؤال #{question.id} به آزمون رسمی {data['exam_id']} اضافه شد",
    )
    await message.answer(
        f"✅ سؤال ثبت شد (#{question.id}).",
        reply_markup=admin_back_button("admin_exams"),
    )
