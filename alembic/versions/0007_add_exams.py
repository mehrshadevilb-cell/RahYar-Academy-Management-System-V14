"""add formal exams tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-14

Merge order: support 0004 → assignments 0005 → quizzes 0006 → exams 0007.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("online_course_id", sa.Integer(), sa.ForeignKey("online_courses.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("pass_score_percent", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_exams_id", "exams", ["id"])
    op.create_index("ix_exams_online_course_id", "exams", ["online_course_id"])

    op.create_table(
        "exam_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_exam_questions_id", "exam_questions", ["id"])
    op.create_index("ix_exam_questions_exam_id", "exam_questions", ["exam_id"])

    op.create_table(
        "exam_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("exam_questions.id"), nullable=False),
        sa.Column("text", sa.String(length=500), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_exam_options_id", "exam_options", ["id"])
    op.create_index("ix_exam_options_question_id", "exam_options", ["question_id"])

    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_exam_attempts_id", "exam_attempts", ["id"])
    op.create_index("ix_exam_attempts_exam_id", "exam_attempts", ["exam_id"])
    op.create_index("ix_exam_attempts_user_id", "exam_attempts", ["user_id"])

    op.create_table(
        "exam_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("exam_attempts.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("exam_questions.id"), nullable=False),
        sa.Column("selected_option_id", sa.Integer(), sa.ForeignKey("exam_options.id"), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_exam_attempt_question"),
    )
    op.create_index("ix_exam_answers_id", "exam_answers", ["id"])
    op.create_index("ix_exam_answers_attempt_id", "exam_answers", ["attempt_id"])
    op.create_index("ix_exam_answers_question_id", "exam_answers", ["question_id"])


def downgrade() -> None:
    op.drop_table("exam_answers")
    op.drop_table("exam_attempts")
    op.drop_table("exam_options")
    op.drop_table("exam_questions")
    op.drop_table("exams")
