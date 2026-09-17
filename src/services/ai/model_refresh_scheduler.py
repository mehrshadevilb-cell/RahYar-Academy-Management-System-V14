from __future__ import annotations

import asyncio
import logging
import os

from src.database.session import SessionLocal
from src.services.ai.model_service import AIModelService

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 6 * 60 * 60


class AIModelRefreshScheduler:
    """Continuously discover providers/models and probe their live availability."""

    def __init__(self, interval_seconds: int | None = None) -> None:
        configured = interval_seconds or int(
            os.getenv("AI_MODEL_REFRESH_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))
        )
        self.interval_seconds = max(15 * 60, configured)
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.interval_seconds)
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("AI model refresh cycle failed")

    async def run_once(self) -> dict:
        def refresh() -> dict:
            db = SessionLocal()
            try:
                service = AIModelService(db)
                sync_results = service.sync_all_active_providers()
                selected = service.select_working_default()
                return {
                    "sync": sync_results,
                    "selected_model": selected.model_id if selected else None,
                }
            finally:
                db.close()

        result = await asyncio.to_thread(refresh)
        logger.info("AI provider/model scan completed: %s", result)
        return result
