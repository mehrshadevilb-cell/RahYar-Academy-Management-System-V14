"""Lightweight production health checks for the academy owner."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import inspect, text

from src.database.connection import engine

CRITICAL_RESERVATION_COLUMNS = (
    "reminder_1h_sent",
    "reminder_1d_sent",
    "reminder_due_sent",
)


def _build_id() -> str:
    env_id = (os.getenv("RAHYAR_BUILD_ID") or "").strip()
    if env_id:
        return env_id
    marker = Path("/tmp/rahyar-build-id.txt")
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip() or "unknown"
    local = Path(__file__).resolve().parents[2] / "docker-build-id.txt"
    if local.is_file():
        return local.read_text(encoding="utf-8").strip() or "unknown"
    return "unknown"


@dataclass(frozen=True)
class SystemHealthReport:
    build_id: str
    database_ok: bool
    database_error: str | None
    reservation_columns_ok: bool
    missing_columns: tuple[str, ...]
    dialect: str

    def format_persian(self) -> str:
        db_line = "✅ اتصال دیتابیس برقرار است" if self.database_ok else f"❌ دیتابیس: {self.database_error}"
        if self.reservation_columns_ok:
            col_line = "✅ ستون‌های یادآوری رزرو کامل است"
        else:
            missing = ", ".join(self.missing_columns) or "—"
            col_line = f"❌ ستون ناقص: {missing}"
        return (
            f"🩺 وضعیت سیستم\n\n"
            f"🏷 Build: {self.build_id}\n"
            f"🗄 Engine: {self.dialect}\n\n"
            f"{db_line}\n"
            f"{col_line}\n\n"
            "اگر ستون ناقص است، یک‌بار کانتینر را ری‌استارت کنید "
            "تا schema_guard و alembic اجرا شوند."
        )


class SystemHealthService:
    def check(self) -> SystemHealthReport:
        dialect = engine.dialect.name
        database_ok = False
        database_error = None
        missing: list[str] = []

        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                database_ok = True
                insp = inspect(conn)
                if "reservations" in insp.get_table_names():
                    cols = {c["name"] for c in insp.get_columns("reservations")}
                    missing = [c for c in CRITICAL_RESERVATION_COLUMNS if c not in cols]
                else:
                    missing = list(CRITICAL_RESERVATION_COLUMNS)
        except Exception as exc:
            database_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            missing = list(CRITICAL_RESERVATION_COLUMNS)

        return SystemHealthReport(
            build_id=_build_id(),
            database_ok=database_ok,
            database_error=database_error,
            reservation_columns_ok=database_ok and not missing,
            missing_columns=tuple(missing),
            dialect=dialect,
        )
