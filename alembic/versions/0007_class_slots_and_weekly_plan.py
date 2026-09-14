"""class slots + weekly payment model value

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL enum extension for PaymentModel.WEEKLY — best-effort.
    # SQLite / fresh installs rely on SQLAlchemy create; production PG needs ALTER.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE paymentmodel ADD VALUE IF NOT EXISTS 'weekly'")

    op.create_table(
        "class_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "online_course_id",
            sa.Integer(),
            sa.ForeignKey("online_courses.id"),
            nullable=False,
        ),
        sa.Column("slot_date", sa.String(length=20), nullable=False),
        sa.Column("slot_time", sa.String(length=10), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("booked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_class_slots_id", "class_slots", ["id"])
    op.create_index("ix_class_slots_online_course_id", "class_slots", ["online_course_id"])


def downgrade() -> None:
    op.drop_index("ix_class_slots_online_course_id", table_name="class_slots")
    op.drop_index("ix_class_slots_id", table_name="class_slots")
    op.drop_table("class_slots")
