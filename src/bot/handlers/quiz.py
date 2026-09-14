from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.quiz_keyboard import (
    question_options_keyboard,
    student_quizzes_keyboard,
)
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.profile_service import ProfileService
from src.services.quiz_service import QuizService, QuizServiceError

router = Router()
quiz_service = QuizService()
enrollment_service = OnlineEnrollmentService()
profile_service = ProfileService()


@router.message(F.text == "❓ آزمون‌ها")
async def student_quiz_menu(message: Message, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    enrollments = enrollment_service.get_active_by_user(db, user.id)
    if not enrollments:
        await message.answer("شما در کلاس آنلاینی ثبت‌نام نیستید.")
        return

    seen: set[int] = set()
    quizzes = []
    for e in enrollments:
        if e.online_course_id in seen:
            continue
        seen.add(e.online_course_id)
        quizzes.extend(quiz_service.list_for_course(db, e.online_course_id, active_only=True))

    if not quizzes:
        await message.answer("آزمون فعالی برای کلاس‌های شما ثبت نشده است.")
        return

    await message.answer(
        "❓ آزمون‌های فعال:\nیکی را انتخاب کنید:",
        reply_markup=student_quizzes_keyboard(quizzes),
    )


@router.callback_query(F.data.startswith("quiz_start_"))
async def quiz_start(callback: CallbackQuery, db):
    quiz_id = int(callback.data.replace("quiz_start_", ""))
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not user:
        await callback.answer("ابتدا /start", show_alert=True)
        return

    try:
        attempt = quiz_service.start_attempt(db, quiz_id=quiz_id, user_id=user.id)
    except QuizServiceError as exc:
        mapping = {
            "quiz_unavailable": "آزمون در دسترس نیست",
            "quiz_empty": "آزمون هنوز سؤالی ندارد",
            "not_enrolled": "شما در این کلاس ثبت‌نام فعال ندارید",
        }
        await callback.answer(mapping.get(str(exc), "خطا"), show_alert=True)
        return

    question = quiz_service.next_unanswered_question(db, attempt.id)
    if not question:
        await callback.message.answer(
            f"✅ این آزمون را قبلاً تمام کرده‌اید.\n"
            f"نمره: {attempt.score}/{attempt.total_questions}"
        )
        await callback.answer()
        return

    await callback.message.answer(
        f"❓ {question.text}",
        reply_markup=question_options_keyboard(attempt.id, question),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quiz_ans_"))
async def quiz_answer(callback: CallbackQuery, db):
    # quiz_ans_{attempt_id}_{question_id}_{option_id}
    parts = callback.data.split("_")
    if len(parts) != 5:
        await callback.answer("داده نامعتبر", show_alert=True)
        return
    _, _, attempt_id_s, question_id_s, option_id_s = parts
    attempt_id, question_id, option_id = int(attempt_id_s), int(question_id_s), int(option_id_s)

    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not user:
        await callback.answer("ابتدا /start", show_alert=True)
        return

    try:
        attempt, is_correct, done = quiz_service.answer(
            db,
            attempt_id=attempt_id,
            question_id=question_id,
            option_id=option_id,
            user_id=user.id,
        )
    except QuizServiceError as exc:
        mapping = {
            "already_answered": "این سؤال را قبلاً پاسخ داده‌اید",
            "already_completed": "آزمون تمام شده است",
            "attempt_not_found": "تلاش پیدا نشد",
            "invalid_option": "گزینه نامعتبر",
        }
        await callback.answer(mapping.get(str(exc), "خطا"), show_alert=True)
        return

    feedback = "✅ درست" if is_correct else "❌ نادرست"
    await callback.answer(feedback)

    if done:
        await callback.message.edit_text(
            f"🏁 آزمون تمام شد\n\nنمره شما: {attempt.score} از {attempt.total_questions}"
        )
        return

    nxt = quiz_service.next_unanswered_question(db, attempt.id)
    if nxt:
        await callback.message.edit_text(
            f"❓ {nxt.text}",
            reply_markup=question_options_keyboard(attempt.id, nxt),
        )
