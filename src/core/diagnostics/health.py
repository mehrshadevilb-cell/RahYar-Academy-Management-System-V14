"""Runtime dependency diagnostics for production deployments."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from typing import Any

from sqlalchemy import text

from src.database.session import SessionLocal


async def _check_redis() -> str:
    """Check Redis only when the deployment configured it as a dependency."""
    redis_url = (os.getenv("REDIS_URL") or "").strip()
    if not redis_url:
        return "disabled"
    try:
        from redis import Redis

        client = Redis.from_url(redis_url, decode_responses=True, socket_timeout=2)
        client.ping()
        return "ok"
    except Exception:
        return "error"


def _telegram_status() -> str:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    return "ok" if re.fullmatch(r"\d{6,15}:[A-Za-z0-9_-]{20,}", token) else "disabled"


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
        "redis": await _check_redis(),
        "telegram": _telegram_status(),
    }

    return {
        "ok": all(value in {"ok", "disabled"} for value in checks.values()),
        "build": build_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
