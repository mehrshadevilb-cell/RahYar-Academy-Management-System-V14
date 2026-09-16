"""Runtime dependency diagnostics for production deployments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


async def build_health_report(build_id: str = "unknown") -> dict[str, Any]:
    """Return a safe health payload.

    Dependency checks are intentionally isolated here so they can be expanded
    without increasing startup complexity in main.py.
    """
    return {
        "ok": True,
        "build": build_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "application": "ok",
            "database": "pending",
            "redis": "pending",
            "telegram": "pending",
        },
    }
