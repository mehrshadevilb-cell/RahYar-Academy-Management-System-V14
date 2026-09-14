from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.keyboards.quiz_keyboard import admin_quiz_home_keyboard
from src.bot.states.quiz_states import AdminQuizState
from src.core.config.settings import get_settings
from src.core.constants import admin_actions
from src.services.admin_log_service import AdminLogService
from src.services.online_course_service import OnlineCourseService
from src.services.quiz_service import QuizService, QuizServiceError

router = Router()
settings = get_settings()
quiz_service = QuizService()
online_course_service = OnlineCourseService()
admin_log_service = AdminLogService()


def _is_owner(user_id: int) -> bool:
    return bool(settings.OWNER_ID) and user_id == settings.OWNER_ID


@router.callback_query(F.data == "admin_quizzes")
async def admin_quiz_home(callback: CallbackQuery):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.message.edit_text(
        "❓ مدیریت آزمون‌ها:",
        reply_markup=admin_quiz_home_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_quiz_create")
async def admin_quiz_create_start(callback: CallbackQuery, state: FSMContext, db):
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
    await state.set_state(AdminQuizState.waiting_course_id)
    await callback.message.answer("\n".join(lines))
    await callback.answer()


@router.message(AdminQuizState.waiting_course_id)
async def admin_quiz_course_id(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("فقط عدد شناسه:")
        return
    course = online_course_service.get_course_by_id(db, int(raw))
    if not course:
        await message.answer("کلاس پیدا نشد:")
        return
    await state.update_data(online_course_id=course.id)
    await state.set_state(AdminQuizState.waiting_title)
    await message.answer(f"عنوان آزمون برای «{course.name}»:")


@router.message(AdminQuizState.waiting_title)
async def admin_quiz_title(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    data = await state.get_data()
    await state.clear()
    try:
        quiz = quiz_service.create_quiz(
            db,
            online_course_id=data["online_course_id"],
            title=(message.text or "").strip(),
        )
    except QuizServiceError as exc:
        await message.answer(f"❌ {exc}")
        return

    admin_log_service.log(
        db,
        message.from_user.id,
        admin_actions.QUIZ_CREATE,
        f"آزمون «{quiz.title}» #{quiz.id} ساخته شد",
    )
    await message.answer(
        f"✅ آزمون #{quiz.id} ساخته شد. از منوی آزمون‌ها سؤال اضافه کنید.",
        reply_markup=admin_back_button("admin_quizzes"),
    )


@router.callback_query(F.data == "admin_quiz_add_q")
async def admin_quiz_add_q_start(callback: CallbackQuery, state: FSMContext):
    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminQuizState.waiting_question_text)
    await state.update_data(quiz_id=None)
    await callback.message.answer(
        "شناسه آزمون و متن سؤال را در دو خط بفرستید:\n"
        "مثال:\n3\nکدام گزینه درباره اکولایزر درست است؟"
    )
    await callback.answer()


@router.message(AdminQuizState.waiting_question_text)
async def admin_quiz_question_text(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    text = (message.text or "").strip()
    lines = text.split("\n", 1)
    if len(lines) < 2 or not lines[0].strip().isdigit():
        await message.answer("فرمت: خط اول شناسه آزمون، خط دوم متن سؤال")
        return
    await state.update_data(quiz_id=int(lines[0].strip()), question_text=lines[1].strip())
    await state.set_state(AdminQuizState.waiting_options)
    await message.answer(
        "گزینه‌ها را هر کدام در یک خط بفرستید (۲ تا ۶ گزینه):"
    )


@router.message(AdminQuizState.waiting_options)
async def admin_quiz_options(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    options = [ln.strip() for ln in (message.text or "").splitlines() if ln.strip()]
    if len(options) < 2:
        await message.answer("حداقل ۲ گزینه لازم است.")
        return
    await state.update_data(options=options)
    await state.set_state(AdminQuizState.waiting_correct_index)
    numbered = "\n".join(f"{i}: {o}" for i, o in enumerate(options))
    await message.answer(f"شماره گزینه درست را بفرستید (از ۰):\n{numbered}")


@router.message(AdminQuizState.waiting_correct_index)
async def admin_quiz_correct(message: Message, state: FSMContext, db):
    if not _is_owner(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("فقط عدد:")
        return
    data = await state.get_data()
    await state.clear()
    try:
        question = quiz_service.add_question(
            db,
            quiz_id=data["quiz_id"],
            text=data["question_text"],
            options=data["options"],
            correct_index=int(raw),
        )
    except QuizServiceError as exc:
        await message.answer(f"❌ {exc}")
        return

    admin_log_service.log(
        db,
        message.from_user.id,
        admin_actions.QUIZ_QUESTION_ADD,
        f"سؤال #{question.id} به آزمون {data['quiz_id']} اضافه شد",
    )
    await message.answer(
        f"✅ سؤال ثبت شد (#{question.id}).",
        reply_markup=admin_back_button("admin_quizzes"),
    )
