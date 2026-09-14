from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.database.models.exam import Exam, ExamQuestion


def student_exams_keyboard(exams: list[Exam]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📋 {e.title[:40]}",
                callback_data=f"exam_start_{e.id}",
            )
        ]
        for e in exams
    ]
    if not rows:
        rows = [[InlineKeyboardButton(text="—", callback_data="noop")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def exam_options_keyboard(attempt_id: int, question: ExamQuestion) -> InlineKeyboardMarkup:
    rows = []
    for opt in sorted(question.options, key=lambda o: o.sort_order):
        rows.append(
            [
                InlineKeyboardButton(
                    text=opt.text[:60],
                    callback_data=f"exam_ans_{attempt_id}_{question.id}_{opt.id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_exam_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ آزمون رسمی جدید", callback_data="admin_exam_create"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ افزودن سؤال", callback_data="admin_exam_add_q"
                )
            ],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")],
        ]
    )
