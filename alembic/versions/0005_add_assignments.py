"""Reconcile assignments migration with the metadata-backed baseline.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-14

The 0001 baseline is generated from Base.metadata and already contains the
assignment tables. Creating them again in 0005 makes a fresh migration chain
fail with "table assignments already exists". Keep 0005 as a compatibility
checkpoint; future changes to assignments must use a new explicit migration.
"""
from typing import Sequence, Union

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # assignments and assignment_submissions are already created by 0001.
    pass


def downgrade() -> None:
    # 0001 owns these tables, so 0005 must never remove them.
    pass
