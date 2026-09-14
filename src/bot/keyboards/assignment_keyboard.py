from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.database.models.assignment import Assignment, AssignmentSubmission


def student_assignments_keyboard(assignments: list[Assignment]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"📝 {a.title[:40]}",
                callback_data=f"asg_view_{a.id}",
            )
        ]
        for a in assignments
    ]
    if not rows:
        rows = [[InlineKeyboardButton(text="—", callback_data="noop")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def student_assignment_detail_keyboard(assignment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 ارسال پاسخ",
                    callback_data=f"asg_submit_{assignment_id}",
                )
            ]
        ]
    )


def admin_pending_submissions_keyboard(
    submissions: list[AssignmentSubmission],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"#{s.id} — {s.content.replace(chr(10), ' ')[:35]}",
                callback_data=f"asg_admin_view_{s.id}",
            )
        ]
        for s in submissions
    ]
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_submission_actions_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ بررسی / نمره",
                    callback_data=f"asg_review_{submission_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ بازگشت برای اصلاح",
                    callback_data=f"asg_return_{submission_id}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ لیست", callback_data="admin_assignments")],
        ]
    )


def admin_assignments_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 ارسال‌های در انتظار",
                    callback_data="admin_asg_pending",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ تکلیف جدید",
                    callback_data="admin_asg_create",
                )
            ],
            [InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_home")],
        ]
    )
