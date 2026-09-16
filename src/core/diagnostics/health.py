"""Runtime dependency diagnostics for production deployments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from src.database.session import SessionLocal


async def _check_database() -> str:
    """Check database availability without breaking the health endpoint."""
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def build_health_report(build_id: str = "unknown") -> dict[str, Any]:
    """Return production health information.

    Checks are isolated from application startup so monitoring failures do not
    affect bot availability.
    """
    database_status = await _check_database()

    checks = {
        "application": "ok",
        "database": database_status,
        "redis": "pending",
        "telegram": "pending",
    }

    return {
        "ok": all(value in {"ok", "pending"} for value in checks.values()),
        "build": build_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
