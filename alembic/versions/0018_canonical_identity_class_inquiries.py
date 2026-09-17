"""add shared class inquiries for canonical users

Revision ID: 0018
Revises: 0017
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "class_inquiries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("online_course_id", sa.Integer(), sa.ForeignKey("online_courses.id"), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="website"),
        sa.Column("requested_plan", sa.String(length=30), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "REVIEWING", "APPROVED", "REJECTED", "ENROLLED", name="classinquirystatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("reviewed_by_telegram_id", sa.String(length=50), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_class_inquiries_id", "class_inquiries", ["id"])
    op.create_index("ix_class_inquiries_user_id", "class_inquiries", ["user_id"])
    op.create_index("ix_class_inquiries_online_course_id", "class_inquiries", ["online_course_id"])
    op.create_index("ix_class_inquiries_status", "class_inquiries", ["status"])
    op.create_index("ix_class_inquiries_user_status", "class_inquiries", ["user_id", "status"])
    op.create_index("ix_class_inquiries_course_status", "class_inquiries", ["online_course_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_class_inquiries_course_status", table_name="class_inquiries")
    op.drop_index("ix_class_inquiries_user_status", table_name="class_inquiries")
    op.drop_index("ix_class_inquiries_status", table_name="class_inquiries")
    op.drop_index("ix_class_inquiries_online_course_id", table_name="class_inquiries")
    op.drop_index("ix_class_inquiries_user_id", table_name="class_inquiries")
    op.drop_index("ix_class_inquiries_id", table_name="class_inquiries")
    op.drop_table("class_inquiries")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="classinquirystatus").drop(bind, checkfirst=True)
