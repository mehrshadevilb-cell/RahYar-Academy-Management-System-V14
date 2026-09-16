"""Continuous fastest-model probe for the shared AI provider router."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from src.ai.latency_aware_provider_router import LatencyAwareAIProviderRouter
from src.core.config.settings import get_settings

logger = logging.getLogger("rahyar.ai.model_speed_monitor")


class ModelSpeedMonitor:
    def __init__(self, router: LatencyAwareAIProviderRouter | None = None) -> None:
        self.settings = get_settings()
        self.router = router or LatencyAwareAIProviderRouter()
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_snapshot: list[dict[str, Any]] = []
        self._fastest: tuple[str, str] | None = None

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.settings, "AI_MODEL_CONTINUOUS_PROBE_ENABLED", True))

    @property
    def interval_seconds(self) -> float:
        raw = getattr(self.settings, "AI_MODEL_PROBE_INTERVAL_SECONDS", 15)
        try:
            return max(5.0, float(raw))
        except (TypeError, ValueError):
            return 15.0

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self._last_snapshot)

    def fastest_route(self) -> tuple[str, str] | None:
        return self._fastest

    def _probe_once(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        providers = self.router.providers()
        candidates = self.router._ordered_candidates(providers)
        for provider, model in candidates[:12]:
            key = f"{provider.name}:{model}"
            row: dict[str, Any] = {
                "provider": provider.name,
                "model": model,
                "ok": False,
                "latency_ms": 0,
                "status": "unknown",
            }
            started = time.perf_counter()
            try:
                status, latency, text = self.router._test_request(provider, model, timeout=8)
                row.update(ok=True, status="ok", latency_ms=latency, response=(text or "")[:80])
                if hasattr(self.router, "record_probe_latency"):
                    self.router.record_probe_latency(provider.name, model, float(latency))
                self.router._model_cooldown_until.pop(key, None)
            except Exception as exc:  # noqa: BLE001
                elapsed = round((time.perf_counter() - started) * 1000)
                row.update(latency_ms=elapsed, status=f"{type(exc).__name__}:{str(exc)[:120]}")
                msg = str(exc).lower()
                if "404" in msg or "not found" in msg:
                    self.router._model_cooldown_until[key] = time.time() + 3600
            results.append(row)

        results.sort(key=lambda r: (not r["ok"], r["latency_ms"], r["provider"], r["model"]))
        self._last_snapshot = results
        healthy = [r for r in results if r["ok"]]
        if healthy:
            best = healthy[0]
            self._fastest = (str(best["provider"]), str(best["model"]))
            if hasattr(self.router, "prefer_route"):
                self.router.prefer_route(str(best["provider"]), str(best["model"]))
        else:
            self._fastest = None
        return results

    async def _loop(self) -> None:
        logger.info("ModelSpeedMonitor started interval=%ss enabled=%s", self.interval_seconds, self.enabled)
        while not self._stop.is_set():
            if self.enabled:
                try:
                    await asyncio.to_thread(self._probe_once)
                except Exception:
                    logger.exception("ModelSpeedMonitor probe failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue
        logger.info("ModelSpeedMonitor stopped")

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="rahyar-model-speed-monitor")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None


model_speed_monitor = ModelSpeedMonitor()
