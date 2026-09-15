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

    def _sync_in_thread(self, since: datetime) -> tuple[list[dict], dict | None, set[int]]:
        db = SessionLocal()
        try:
            self.service.ingest_official_sources(db)
            items = db.scalars(select(KnowledgeItem).where(KnowledgeItem.created_at >= since).order_by(KnowledgeItem.created_at)).all()
            new_items = [
                {"title": item.title, "text": (item.translated_text or item.summary or item.raw_text)[:2800], "url": item.source_url}
                for item in items if item.source_type != "telegram"
            ]
            group_ids = {int(value) for value in self.settings.knowledge_group_ids}
            if not group_ids:
                group_ids = {int(value) for value in db.scalars(select(KnowledgeItem.source_chat_id).where(KnowledgeItem.source_type == "telegram", KnowledgeItem.source_chat_id.is_not(None)).distinct()).all()}
            quiz = None
            if self.settings.KNOWLEDGE_AUTO_QUIZ:
                before = db.scalar(select(QuizQuestion.id).order_by(desc(QuizQuestion.created_at)))
                self.service.generate_quiz(db, 5)
                after = db.scalar(select(QuizQuestion).order_by(desc(QuizQuestion.created_at)))
                if after and (before is None or after.id != before):
                    quiz = {"question": after.question[:280], "options": [after.option_a, after.option_b, after.option_c, after.option_d], "correct": after.correct_option - 1, "explanation": (after.explanation or "")[:200]}
            return new_items, quiz, group_ids
        finally:
            db.close()

    async def _publish(self, new_items: list[dict], quiz: dict | None, groups: set[int]) -> None:
        if not groups:
            return
        for item in new_items:
            message = "🧠 <b>مطلب آموزشی جدید</b>\n━━━━━━━━━━━━━━━━━━\n📌 <b>%s</b>\n\n%s\n\n🔗 منبع: %s" % (item["title"] or "Audio Production", item["text"], item["url"] or "")
            for chat_id in groups:
                try:
                    await self.bot.send_message(chat_id, message, parse_mode="HTML", disable_web_page_preview=True)
                except Exception:
                    pass
        if quiz:
            for chat_id in groups:
                try:
                    await self.bot.send_poll(chat_id=chat_id, question="🧠 کوییز راه‌یار\n\n" + quiz["question"], options=quiz["options"], type="quiz", correct_option_id=quiz["correct"], explanation=quiz["explanation"], is_anonymous=False)
                except Exception:
                    pass

    async def _run_once(self) -> None:
        started = datetime.utcnow() - timedelta(seconds=5)
        new_items, quiz, groups = await asyncio.to_thread(self._sync_in_thread, started)
        await self._publish(new_items, quiz, groups)

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
