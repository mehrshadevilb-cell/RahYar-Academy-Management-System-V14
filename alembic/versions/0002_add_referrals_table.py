"""add referrals table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --------------------------------------------------------------------------
# WHY THIS MIGRATION USES RAW SQL ON POSTGRES (do not "simplify" this back
# to a plain op.create_table(..., sa.Enum(...)) call - that was tried twice
# and fails on redeploy):
#
# src/database/models/referral.py defines:
#     status: Mapped[ReferralStatus] = mapped_column(Enum(ReferralStatus), ...)
#
# alembic/env.py imports that model (`from src.database.models.referral
# import Referral`) so Base.metadata has this Enum column registered
# *before any migration runs*. Because of that, SQLAlchemy's postgres
# dialect attaches a "before_create" DDL event to any Table containing a
# column of type ENUM(name="referralstatus") that unconditionally issues
#     CREATE TYPE referralstatus AS ENUM ('pending', 'rewarded')
# with checkfirst=False - regardless of passing create_type=False on a
# *separate* Enum instance used only inside this migration file. We
# confirmed this empirically: setting create_type=False on a fresh
# postgresql.ENUM(...) object still produced
#     psycopg.errors.DuplicateObject: type "referralstatus" already exists
# on any redeploy where a previous (possibly partially-failed) run had
# already created the type but the table/alembic_version bump didn't
# complete.
#
# The fix: on PostgreSQL, create the type and table with raw, explicitly
# idempotent SQL, bypassing SQLAlchemy's enum-in-create_table DDL
# machinery entirely. On SQLite (local dev / tests), there is no native
# CREATE TYPE step, so the plain ORM-based path is safe and kept as-is.
# --------------------------------------------------------------------------


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        bind.execute(sa.text(
            """
            DO $$
            BEGIN
                CREATE TYPE referralstatus AS ENUM ('pending', 'rewarded');
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        ))
        bind.execute(sa.text(
            """
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BigInteger NOT NULL REFERENCES users(id),
                referred_id BigInteger NOT NULL UNIQUE REFERENCES users(id),
                status referralstatus NOT NULL DEFAULT 'pending',
                reward_discount_code_id BigInteger REFERENCES discount_codes(id),
                created_at TIMESTAMP NOT NULL,
                rewarded_at TIMESTAMP
            )
            """
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_referrals_id ON referrals (id)"
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_referrals_referrer_id "
            "ON referrals (referrer_id)"
        ))
    else:
        op.create_table(
            "referrals",
            sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
            sa.Column(
                "referrer_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "referred_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "status",
                sa.Enum("pending", "rewarded", name="referralstatus"),
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "reward_discount_code_id",
                sa.BigInteger(),
                sa.ForeignKey("discount_codes.id"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("rewarded_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("DROP TABLE IF EXISTS referrals"))
        bind.execute(sa.text("DROP TYPE IF EXISTS referralstatus"))
    else:
        op.drop_table("referrals")
