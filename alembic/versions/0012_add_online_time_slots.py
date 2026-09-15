"""Merge the online time-slot migration heads.

Revision ID: 0012
Revises: 0011, 0011_online_slots

The table itself is created by the online-slot head when needed. The merge
revision must not recreate or destroy it.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = ("0011", "0011_online_slots")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merge-only revision. Both parent revisions independently converge on
    # the same online_time_slots schema, with guards for pre-existing tables.
    return


def downgrade() -> None:
    # Merge revisions should only move Alembic's version pointer. The table is
    # owned by the 0011_online_slots branch and must remain intact here.
    return
