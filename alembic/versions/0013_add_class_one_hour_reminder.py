"""add one-hour class reminder flag"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "reminder_1h_sent" not in {column["name"] for column in inspect(op.get_bind()).get_columns("reservations")}:
        op.add_column("reservations", sa.Column("reminder_1h_sent", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    if "reminder_1h_sent" in {column["name"] for column in inspect(op.get_bind()).get_columns("reservations")}:
        op.drop_column("reservations", "reminder_1h_sent")
