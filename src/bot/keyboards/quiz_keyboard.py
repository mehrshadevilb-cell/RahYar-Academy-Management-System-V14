from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.database.models.quiz import Quiz, QuizQuestion


def student_quizzes_keyboard(quizzes: list[Quiz]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"❓ {q.title[:40]}",
                callback_data=f"quiz_start_{q.id}",
            )
        ]
        for q in quizzes
    ]
    if not rows:
        rows = [[InlineKeyboardButton(text="—", callback_data="noop")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def question_options_keyboard(
    attempt_id: int, question: QuizQuestion
) -> InlineKeyboardMarkup:
    rows = []
    for opt in sorted(question.options, key=lambda o: o.sort_order):
        rows.append(
            [
                InlineKeyboardButton(
                    text=opt.text[:60],
                    callback_data=f"quiz_ans_{attempt_id}_{question.id}_{opt.id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_quiz_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ آزمون جدید", callback_data="admin_quiz_create"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ افزودن سؤال", callback_data="admin_quiz_add_q"
                )
            ],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")],
        ]
    )
