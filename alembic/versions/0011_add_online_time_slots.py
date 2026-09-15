"""Add online time slots table.

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "online_time_slots" in inspector.get_table_names():
        return

    op.create_table(
        "online_time_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("online_course_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index(
        "ix_online_time_slots_course_id",
        "online_time_slots",
        ["online_course_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_online_time_slots_course_id",
        table_name="online_time_slots",
    )
    op.drop_table("online_time_slots")
