"""Idempotent schema repairs for critical production columns.

Alembic remains the source of truth for intentional schema changes. This module
exists only as a last-resort self-heal when a production database was stamped
to a revision that never actually applied a column (branched heads, partial
deploys, or a failed upgrade that still left the process running).

Keep this list short. Prefer real Alembic migrations for new work.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from src.database.connection import engine

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

_NOTIFICATION_PREFS_DDL_PG = """
CREATE TABLE IF NOT EXISTS notification_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    installment_reminders BOOLEAN NOT NULL DEFAULT true,
    class_reminders BOOLEAN NOT NULL DEFAULT true,
    broadcast_messages BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
)
"""

_NOTIFICATION_PREFS_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS notification_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    installment_reminders BOOLEAN NOT NULL DEFAULT 1,
    class_reminders BOOLEAN NOT NULL DEFAULT 1,
    broadcast_messages BOOLEAN NOT NULL DEFAULT 1,
    updated_at TIMESTAMP
)
"""


def ensure_critical_schema() -> None:
    """Ensure critical columns/tables exist. Safe to call on every process start."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        for table, column, ddl in _CRITICAL_COLUMNS:
            if dialect == "postgresql":
                sql = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}"
                conn.execute(text(sql))
                logger.info("schema_guard: ensured %s.%s", table, column)
            else:
                try:
                    existing = {
                        r[1]
                        for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                    }
                except Exception:
                    existing = set()
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                    logger.info("schema_guard: added %s.%s", table, column)

        # notification_preferences table (user mute settings)
        if dialect == "postgresql":
            conn.execute(text(_NOTIFICATION_PREFS_DDL_PG))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_notification_preferences_user_id "
                    "ON notification_preferences (user_id)"
                )
            )
        else:
            conn.execute(text(_NOTIFICATION_PREFS_DDL_SQLITE))
        logger.info("schema_guard: ensured notification_preferences")
