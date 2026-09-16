"""Continuous AI model speed monitor.

Periodically live-tests every configured model in parallel, records latency,
and pins the Agent router to the fastest model that is currently responding.

Interval is configurable (default 15s). Values below 5s are clamped to avoid
API quota burn; "every second" is intentionally not the production default.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from src.core.config.settings import get_settings
from src.services.ai_agent_runtime import runtime

logger = logging.getLogger("rahyar.ai.model_speed_monitor")


class ContinuousModelSpeedMonitor:
    """Background loop: probe all models → switch Agent to fastest healthy route."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_snapshot: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @property
    def interval_seconds(self) -> int:
        try:
            raw = int(getattr(self.settings, "AI_MODEL_PROBE_INTERVAL_SECONDS", 15) or 15)
        except (TypeError, ValueError):
            raw = 15
        return max(5, min(raw, 3600))

    @property
    def enabled(self) -> bool:
        if not self.settings.AI_AGENT_ENABLED:
            return False
        return bool(getattr(self.settings, "AI_MODEL_CONTINUOUS_PROBE_ENABLED", True))

    def snapshot(self) -> dict[str, Any]:
        return dict(self._last_snapshot)

    def _probe_once(self) -> dict[str, Any]:
        agent = runtime.agent
        health = agent.model_health
        results = health.test_all_parallel(timeout_seconds=12)
        working = [row for row in results if row.get("ok")]
        working.sort(
            key=lambda row: (
                int(row.get("latency_ms") or 10_000),
                0 if row.get("free") else 1,
                str(row.get("provider") or ""),
                str(row.get("model") or ""),
            )
        )
        route = None
        if working:
            best = working[0]
            provider = str(best["provider"])
            model = str(best["model"])
            route = f"{provider}/{model}"
            latency = int(best.get("latency_ms") or 0)
            if hasattr(agent.router, "record_probe_latency"):
                agent.router.record_probe_latency(provider, model, latency)
            for row in working:
                p, m = str(row.get("provider") or ""), str(row.get("model") or "")
                if p and m:
                    agent.router._model_cooldown_until.pop(f"{p}:{m}", None)
                    agent.router._cooldown_until.pop(p, None)
            if hasattr(agent.router, "prefer_route"):
                agent.router.prefer_route(provider, model, latency)
            try:
                from src.database.models.ai_model import AIModel
                from src.database.models.ai_provider import AIProvider
                from src.database.session import SessionLocal
                from src.services.ai.model_service import AIModelService

                db = SessionLocal()
                try:
                    model_row = (
                        db.query(AIModel)
                        .join(AIProvider, AIProvider.id == AIModel.provider_id)
                        .filter(
                            AIProvider.name == provider,
                            AIModel.model_id == model,
                            AIModel.is_active.is_(True),
                            AIProvider.is_active.is_(True),
                        )
                        .first()
                    )
                    if model_row is not None:
                        AIModelService(db).set_default(model_row.id)
                finally:
                    db.close()
            except Exception:
                pass

        snapshot = {
            "at": time.time(),
            "tested": len(results),
            "working": len(working),
            "route": route,
            "fastest_latency_ms": working[0].get("latency_ms") if working else None,
            "results": [
                {
                    "provider": r.get("provider"),
                    "model": r.get("model"),
                    "ok": bool(r.get("ok")),
                    "latency_ms": r.get("latency_ms"),
                    "free": bool(r.get("free")),
                    "status": r.get("status"),
                }
                for r in results
            ],
        }
        self._last_snapshot = snapshot
        if route:
            logger.info(
                "AI speed monitor: fastest route=%s latency_ms=%s working=%s/%s",
                route,
                snapshot["fastest_latency_ms"],
                snapshot["working"],
                snapshot["tested"],
            )
        else:
            logger.warning("AI speed monitor: no responding model (tested=%s)", snapshot["tested"])
        return snapshot

    async def _loop(self) -> None:
        logger.info(
            "AI continuous model speed monitor started (interval=%ss)",
            self.interval_seconds,
        )
        while not self._stop.is_set():
            if self.enabled:
                try:
                    async with self._lock:
                        await asyncio.to_thread(self._probe_once)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("AI speed monitor probe failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        if not self.enabled:
            logger.info("AI continuous model probe disabled")
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="ai-model-speed-monitor")

    async def stop(self) -> None:
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    async def force_probe(self) -> dict[str, Any]:
        async with self._lock:
            return await asyncio.to_thread(self._probe_once)


model_speed_monitor = ContinuousModelSpeedMonitor()
