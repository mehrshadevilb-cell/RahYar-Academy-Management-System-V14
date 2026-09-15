"""add recurring online class time slots"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "online_time_slots" in inspect(bind).get_table_names():
        return
    op.create_table(
        "online_time_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("online_course_id", sa.Integer(), sa.ForeignKey("online_courses.id"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("online_course_id", "weekday", "start_time", "end_time", name="uq_online_slot_window"),
    )
    op.create_index("ix_online_time_slots_id", "online_time_slots", ["id"])
    op.create_index("ix_online_time_slots_online_course_id", "online_time_slots", ["online_course_id"])


def downgrade() -> None:
    op.drop_index("ix_online_time_slots_online_course_id", table_name="online_time_slots")
    op.drop_index("ix_online_time_slots_id", table_name="online_time_slots")
    op.drop_table("online_time_slots")
