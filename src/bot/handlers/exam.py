from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.exam_keyboard import exam_options_keyboard, student_exams_keyboard
from src.services.exam_service import ExamService, ExamServiceError
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.profile_service import ProfileService

router = Router()
exam_service = ExamService()
enrollment_service = OnlineEnrollmentService()
profile_service = ProfileService()


@router.message(F.text == "📋 آزمون رسمی")
async def student_exam_menu(message: Message, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    enrollments = enrollment_service.get_active_by_user(db, user.id)
    if not enrollments:
        await message.answer("شما در کلاس آنلاینی ثبت‌نام نیستید.")
        return

    seen: set[int] = set()
    exams = []
    for e in enrollments:
        if e.online_course_id in seen:
            continue
        seen.add(e.online_course_id)
        exams.extend(exam_service.list_for_course(db, e.online_course_id, active_only=True))

    if not exams:
        await message.answer("آزمون رسمی فعالی برای کلاس‌های شما ثبت نشده است.")
        return

    await message.answer(
        "📋 آزمون‌های رسمی:\n"
        "توجه: نتیجه فقط در پایان نمایش داده می‌شود.",
        reply_markup=student_exams_keyboard(exams),
    )


@router.callback_query(F.data.startswith("exam_start_"))
async def exam_start(callback: CallbackQuery, db):
    exam_id = int(callback.data.replace("exam_start_", ""))
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not user:
        await callback.answer("ابتدا /start", show_alert=True)
        return

    try:
        attempt = exam_service.start_attempt(db, exam_id=exam_id, user_id=user.id)
    except ExamServiceError as exc:
        mapping = {
            "exam_unavailable": "آزمون در دسترس نیست",
            "exam_empty": "آزمون هنوز سؤالی ندارد",
            "not_enrolled": "ثبت‌نام فعال ندارید",
            "attempts_exhausted": "سقف تعداد تلاش تمام شده است",
        }
        await callback.answer(mapping.get(str(exc), "خطا"), show_alert=True)
        return

    question = exam_service.next_unanswered_question(db, attempt.id)
    if not question:
        result = "قبول" if attempt.passed else "مردود"
        await callback.message.answer(
            f"این آزمون را قبلاً تمام کرده‌اید.\n"
            f"نمره: {attempt.score_percent}% ({attempt.score}/{attempt.total_questions}) — {result}"
        )
        await callback.answer()
        return

    exam = exam_service.get_exam(db, exam_id)
    pass_line = f"حد نصاب قبولی: {exam.pass_score_percent}%" if exam else ""
    await callback.message.answer(
        f"📋 شروع آزمون\n{pass_line}\n\n❓ {question.text}",
        reply_markup=exam_options_keyboard(attempt.id, question),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("exam_ans_"))
async def exam_answer(callback: CallbackQuery, db):
    parts = callback.data.split("_")
    if len(parts) != 5:
        await callback.answer("داده نامعتبر", show_alert=True)
        return
    _, _, attempt_id_s, question_id_s, option_id_s = parts
    attempt_id = int(attempt_id_s)
    question_id = int(question_id_s)
    option_id = int(option_id_s)

    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not user:
        await callback.answer("ابتدا /start", show_alert=True)
        return

    try:
        attempt, done = exam_service.answer(
            db,
            attempt_id=attempt_id,
            question_id=question_id,
            option_id=option_id,
            user_id=user.id,
        )
    except ExamServiceError as exc:
        mapping = {
            "already_answered": "این سؤال را قبلاً پاسخ داده‌اید",
            "already_completed": "آزمون تمام شده",
            "attempt_not_found": "تلاش پیدا نشد",
            "invalid_option": "گزینه نامعتبر",
        }
        await callback.answer(mapping.get(str(exc), "خطا"), show_alert=True)
        return

    # Formal exam: no per-question correctness reveal
    await callback.answer("ثبت شد")

    if done:
        result = "✅ قبول" if attempt.passed else "❌ مردود"
        await callback.message.edit_text(
            f"🏁 آزمون به پایان رسید\n\n"
            f"نمره: {attempt.score_percent}%\n"
            f"صحیح: {attempt.score} از {attempt.total_questions}\n"
            f"نتیجه: {result}"
        )
        return

    nxt = exam_service.next_unanswered_question(db, attempt.id)
    if nxt:
        await callback.message.edit_text(
            f"❓ {nxt.text}",
            reply_markup=exam_options_keyboard(attempt.id, nxt),
        )
