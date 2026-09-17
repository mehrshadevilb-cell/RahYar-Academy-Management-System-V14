"""add privacy-preserving site analytics events

Revision ID: 0019
Revises: 0018
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("path", sa.String(length=240), nullable=False, server_default="/"),
        sa.Column("visitor_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_site_events_id", "site_events", ["id"])
    op.create_index("ix_site_events_event_type", "site_events", ["event_type"])
    op.create_index("ix_site_events_visitor_hash", "site_events", ["visitor_hash"])
    op.create_index("ix_site_events_created_at", "site_events", ["created_at"])
    op.create_index("ix_site_events_type_created", "site_events", ["event_type", "created_at"])
    op.create_index("ix_site_events_path_created", "site_events", ["path", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_site_events_path_created", table_name="site_events")
    op.drop_index("ix_site_events_type_created", table_name="site_events")
    op.drop_index("ix_site_events_created_at", table_name="site_events")
    op.drop_index("ix_site_events_visitor_hash", table_name="site_events")
    op.drop_index("ix_site_events_event_type", table_name="site_events")
    op.drop_index("ix_site_events_id", table_name="site_events")
    op.drop_table("site_events")
