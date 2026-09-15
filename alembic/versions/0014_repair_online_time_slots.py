"""repair deployments missing online_time_slots despite an advanced stamp"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "online_time_slots" not in inspect(bind).get_table_names():
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
    indexes = {item["name"] for item in inspect(bind).get_indexes("online_time_slots")}
    if "ix_online_time_slots_id" not in indexes:
        op.create_index("ix_online_time_slots_id", "online_time_slots", ["id"])
    if "ix_online_time_slots_online_course_id" not in indexes:
        op.create_index("ix_online_time_slots_online_course_id", "online_time_slots", ["online_course_id"])


def downgrade() -> None:
    # Keep the repair migration non-destructive; 0012 owns the original table.
    pass
