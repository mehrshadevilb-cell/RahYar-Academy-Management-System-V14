"""AI health monitoring utilities.

Keeps runtime diagnostics independent from individual agents so chat,
audit and automation flows can share the same health information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ProviderHealth:
    name: str
    healthy: bool = True
    latency_ms: int | None = None
    last_error: str | None = None
    last_success_at: datetime | None = None
    failures: int = 0


class AIHealthMonitor:
    def __init__(self):
        self.providers: dict[str, ProviderHealth] = {}

    def register(self, name: str):
        if name not in self.providers:
            self.providers[name] = ProviderHealth(name=name)

    def success(self, name: str, latency_ms: int | None = None):
        self.register(name)
        item = self.providers[name]
        item.healthy = True
        item.latency_ms = latency_ms
        item.last_error = None
        item.last_success_at = datetime.now(timezone.utc)
        item.failures = 0

    def failure(self, name: str, error: Exception | str):
        self.register(name)
        item = self.providers[name]
        item.healthy = False
        item.last_error = str(error)[:500]
        item.failures += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            name: {
                "healthy": item.healthy,
                "latency_ms": item.latency_ms,
                "failures": item.failures,
                "last_error": item.last_error,
                "last_success_at": item.last_success_at.isoformat()
                if item.last_success_at else None,
            }
            for name, item in self.providers.items()
        }


ai_health_monitor = AIHealthMonitor()
