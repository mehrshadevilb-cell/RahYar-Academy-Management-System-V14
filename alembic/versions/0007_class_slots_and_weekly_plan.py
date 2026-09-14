"""class slots + weekly payment plan + reservation.class_slot_id

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "class_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("online_course_id", sa.Integer(), sa.ForeignKey("online_courses.id"), nullable=False),
        sa.Column("slot_date", sa.String(20), nullable=False),
        sa.Column("slot_time", sa.String(10), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("booked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum("open", "booked", "closed", name="classslotstatus", create_constraint=True),
            nullable=False,
            server_default="open",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_class_slots_online_course_id", "class_slots", ["online_course_id"])

    op.add_column(
        "online_courses",
        sa.Column("weekly_price", sa.Integer(), nullable=True),
    )
    op.add_column(
        "online_courses",
        sa.Column("weekly_sessions", sa.Integer(), nullable=False, server_default="1"),
    )

    # Expand PaymentModel enum with weekly (PostgreSQL requires ALTER TYPE).
    # Using a safe approach: create new type, migrate, drop old.
    op.execute("ALTER TYPE paymentmodel RENAME TO paymentmodel_old")
    op.execute("CREATE TYPE paymentmodel AS ENUM ('weekly', 'monthly', 'term')")
    op.execute(
        "ALTER TABLE online_enrollments "
        "ALTER COLUMN payment_model TYPE paymentmodel "
        "USING payment_model::text::paymentmodel"
    )
    op.execute("DROP TYPE paymentmodel_old")

    op.add_column(
        "reservations",
        sa.Column("class_slot_id", sa.Integer(), sa.ForeignKey("class_slots.id"), nullable=True),
    )
    op.create_index("ix_reservations_class_slot_id", "reservations", ["class_slot_id"])


def downgrade() -> None:
    op.drop_index("ix_reservations_class_slot_id", table_name="reservations")
    op.drop_column("reservations", "class_slot_id")

    op.execute("ALTER TYPE paymentmodel RENAME TO paymentmodel_old")
    op.execute("CREATE TYPE paymentmodel AS ENUM ('monthly', 'term')")
    op.execute(
        "ALTER TABLE online_enrollments "
        "ALTER COLUMN payment_model TYPE paymentmodel "
        "USING CASE WHEN payment_model::text = 'weekly' THEN 'monthly'::paymentmodel "
        "ELSE payment_model::text::paymentmodel END"
    )
    op.execute("DROP TYPE paymentmodel_old")

    op.drop_column("online_courses", "weekly_sessions")
    op.drop_column("online_courses", "weekly_price")

    op.drop_index("ix_class_slots_online_course_id", table_name="class_slots")
    op.drop_table("class_slots")
    op.execute("DROP TYPE IF EXISTS classslotstatus")
