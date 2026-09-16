"""Lightweight runtime metrics helpers.

Keeps observability independent from external monitoring providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RuntimeMetrics:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    counters: dict[str, int] = field(default_factory=dict)

    def increment(self, key: str, amount: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + amount

    def snapshot(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "counters": dict(self.counters),
        }


runtime_metrics = RuntimeMetrics()
