"""Background ingestion scheduler for official learning sources and quizzes."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy import desc, select

from src.core.config.settings import get_settings
from src.database.models.knowledge import KnowledgeItem, QuizQuestion
from src.database.session import SessionLocal
from src.services.knowledge_service import KnowledgeService


class KnowledgeScheduler:
    def __init__(self, bot: Bot) -> None:
        self.settings = get_settings()
        self.bot = bot
        self.service = KnowledgeService()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if not self.settings.KNOWLEDGE_ENABLED or self._task:
            return
        self._task = asyncio.create_task(self._loop(), name="rahyar-knowledge-sync")

    async def _publish_new_items(self, db, since: datetime) -> None:
        groups = self.settings.knowledge_group_ids
        if not groups:
            return
        items = db.scalars(select(KnowledgeItem).where(KnowledgeItem.created_at >= since).order_by(KnowledgeItem.created_at)).all()
        for item in items:
            if item.source_type == "telegram":
                continue
            text = item.translated_text or item.summary or item.raw_text
            message = "🧠 <b>مطلب آموزشی جدید</b>\n━━━━━━━━━━━━━━━━━━\n📌 <b>%s</b>\n\n%s\n\n🔗 منبع: %s" % (item.title or "Audio Production", text[:2800], item.source_url)
            for chat_id in groups:
                try:
                    await self.bot.send_message(chat_id, message, parse_mode="HTML", disable_web_page_preview=True)
                except Exception:
                    pass

    async def _publish_quiz(self, db) -> None:
        groups = self.settings.knowledge_group_ids
        if not groups:
            return
        question = db.scalar(select(QuizQuestion).order_by(desc(QuizQuestion.created_at)))
        if not question:
            return
        options = [question.option_a, question.option_b, question.option_c, question.option_d]
        for chat_id in groups:
            try:
                await self.bot.send_poll(chat_id=chat_id, question="🧠 کوییز راه‌یار\n\n" + question.question[:280], options=options, type="quiz", correct_option_id=question.correct_option - 1, explanation=(question.explanation or "")[:200], is_anonymous=False)
            except Exception:
                pass

    async def _run_once(self) -> None:
        started = datetime.utcnow() - timedelta(seconds=5)
        db = SessionLocal()
        try:
            await asyncio.to_thread(self.service.ingest_official_sources, db)
            await self._publish_new_items(db, started)
            if self.settings.KNOWLEDGE_AUTO_QUIZ:
                before = db.scalar(select(QuizQuestion.id).order_by(desc(QuizQuestion.created_at)))
                await asyncio.to_thread(self.service.generate_quiz, db, 5)
                db.expire_all()
                after = db.scalar(select(QuizQuestion.id).order_by(desc(QuizQuestion.created_at)))
                if after != before:
                    await self._publish_quiz(db)
        finally:
            db.close()

    async def _loop(self) -> None:
        await asyncio.sleep(20)
        while True:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(max(1, self.settings.KNOWLEDGE_FETCH_INTERVAL_HOURS) * 3600)
