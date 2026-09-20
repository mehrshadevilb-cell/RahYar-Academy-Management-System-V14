"""Idempotent schema repairs for critical production tables/columns.

Alembic remains the source of truth for intentional schema changes. This module
exists as a last-resort self-heal when a production database was stamped to a
revision that never actually applied a table/column (branched heads, partial
deploys, or a failed upgrade that still left the process running).

Keep this list short. Prefer real Alembic migrations for new work.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from src.database.base import Base
from src.database.connection import engine

# Import models so Base.metadata is complete before create_all(checkfirst=True).
from src.database.models.user import User  # noqa: F401
from src.database.models.telegram_account import TelegramAccount  # noqa: F401
from src.database.models.course import Course  # noqa: F401
from src.database.models.free_lesson import FreeLesson  # noqa: F401
from src.database.models.student_profile import StudentProfile  # noqa: F401
from src.database.models.enrollment import Enrollment  # noqa: F401
from src.database.models.payment import Payment  # noqa: F401
from src.database.models.payment_card import PaymentCard  # noqa: F401
from src.database.models.spotplayer_course import SpotPlayerCourse  # noqa: F401
from src.database.models.telegram_channel import TelegramChannel  # noqa: F401
from src.database.models.license import License  # noqa: F401
from src.database.models.invite_link import TelegramInviteLink  # noqa: F401
from src.database.models.online_course import OnlineCourse  # noqa: F401
from src.database.models.online_enrollment import OnlineEnrollment  # noqa: F401
from src.database.models.reservation import Reservation  # noqa: F401
from src.database.models.attendance import Attendance  # noqa: F401
from src.database.models.installment import Installment  # noqa: F401
from src.database.models.discount_code import DiscountCode  # noqa: F401
from src.database.models.admin_log import AdminLog  # noqa: F401

logger = logging.getLogger(__name__)

# (table, column, DDL fragment after ADD COLUMN)
_CRITICAL_COLUMNS: tuple[tuple[str, str, str], ...] = (
    (
        "reservations",
        "reminder_1h_sent",
        "BOOLEAN NOT NULL DEFAULT false",
    ),
    (
        "reservations",
        "reminder_1d_sent",
        "BOOLEAN NOT NULL DEFAULT false",
    ),
    (
        "reservations",
        "reminder_due_sent",
        "BOOLEAN NOT NULL DEFAULT false",
    ),
)


def ensure_critical_schema() -> None:
    """Ensure core tables + critical columns exist. Safe on every process start."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        # create_all(checkfirst=True) is a no-op when tables already exist and
        # repairs missing baseline tables after a partial / stamped deploy.
        Base.metadata.create_all(bind=conn, checkfirst=True)
        logger.info("schema_guard: ensured baseline tables via create_all(checkfirst)")

        existing_tables = set(inspect(conn).get_table_names())
        for table, column, ddl in _CRITICAL_COLUMNS:
            if table not in existing_tables:
                logger.warning("schema_guard: skip %s.%s (table missing)", table, column)
                continue
            if dialect == "postgresql":
                sql = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"
                conn.execute(text(sql))
                logger.info("schema_guard: ensured %s.%s", table, column)
            else:
                cols = {row["name"] for row in inspect(conn).get_columns(table)}
                if column not in cols:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                    logger.info("schema_guard: added %s.%s", table, column)
