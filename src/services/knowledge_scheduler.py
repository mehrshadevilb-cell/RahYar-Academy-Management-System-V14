"""Background ingestion scheduler for official learning sources and quizzes."""
from __future__ import annotations

import asyncio

from src.core.config.settings import get_settings
from src.database.session import SessionLocal
from src.services.knowledge_service import KnowledgeService


class KnowledgeScheduler:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.service = KnowledgeService()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if not self.settings.KNOWLEDGE_ENABLED or self._task:
            return
        self._task = asyncio.create_task(self._loop(), name="rahyar-knowledge-sync")

    async def _run_once(self) -> None:
        db = SessionLocal()
        try:
            await asyncio.to_thread(self.service.ingest_official_sources, db)
            if self.settings.KNOWLEDGE_AUTO_QUIZ:
                await asyncio.to_thread(self.service.generate_quiz, db, 5)
        finally:
            db.close()

    async def _loop(self) -> None:
        # Initial sync is intentionally delayed so bot startup is not blocked.
        await asyncio.sleep(20)
        while True:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Knowledge ingestion is non-critical; never take the bot down.
                pass
            await asyncio.sleep(max(1, self.settings.KNOWLEDGE_FETCH_INTERVAL_HOURS) * 3600)
