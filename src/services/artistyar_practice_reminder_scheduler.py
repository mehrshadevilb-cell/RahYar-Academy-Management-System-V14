import asyncio
import logging
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot
from sqlalchemy import text

from src.database.models.telegram_account import TelegramAccount
from src.database.models.user import User, UserRole
from src.database.session import SessionLocal

logger = logging.getLogger(__name__)

TEHRAN_TZ = ZoneInfo("Asia/Tehran")
DEFAULT_INTERVAL_SECONDS = 15 * 60


class ArtistYarPracticeReminderScheduler:
    """
    Sends one daily Telegram encouragement to students who have not completed
    any ArtistYar listening practice that day.

    ArtistYar owns the practice data; RahYar only orchestrates Telegram delivery.
    """

    def __init__(self, bot: Bot, interval_seconds: int = DEFAULT_INTERVAL_SECONDS):
        self.bot = bot
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self.site_url = (os.getenv("ARTISTYAR_PRACTICE_API_URL") or "https://artistyaar.ir").rstrip("/")
        self.secret = (os.getenv("ARTISTYAR_PRACTICE_REMINDER_SECRET") or "").strip()
        self.reminder_hour = max(0, min(23, int(os.getenv("ARTISTYAR_PRACTICE_REMINDER_HOUR", "18"))))
        self.reminder_minute = max(0, min(59, int(os.getenv("ARTISTYAR_PRACTICE_REMINDER_MINUTE", "0"))))

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("ArtistYar practice reminder scheduler started")

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("ArtistYar practice reminder cycle failed")
            await asyncio.sleep(self.interval_seconds)

    def _in_reminder_window(self) -> bool:
        now = datetime.now(TEHRAN_TZ)
        target = now.replace(hour=self.reminder_hour, minute=self.reminder_minute, second=0, microsecond=0)
        return target <= now < target.replace(minute=(self.reminder_minute + 15) % 60)

    def _ensure_log_table(self, db) -> None:
        db.execute(text("""
            create table if not exists artistyar_practice_reminder_log (
                id bigserial primary key,
                telegram_id varchar(50) not null,
                reminder_date date not null,
                sent_at timestamp not null default now(),
                unique (telegram_id, reminder_date)
            )
        """))
        db.commit()

    def _student_telegram_ids(self, db) -> list[str]:
        rows = (
            db.query(TelegramAccount.telegram_id)
            .join(User, User.id == TelegramAccount.user_id)
            .filter(User.role == UserRole.STUDENT, User.is_active.is_(True))
            .all()
        )
        return list(dict.fromkeys(str(row[0]) for row in rows if row[0]))

    def _unsent_ids(self, db, telegram_ids: list[str], today: date) -> list[str]:
        if not telegram_ids:
            return []
        rows = db.execute(
            text("select telegram_id from artistyar_practice_reminder_log where reminder_date = :today"),
            {"today": today},
        ).all()
        sent = {str(row[0]) for row in rows}
        return [telegram_id for telegram_id in telegram_ids if telegram_id not in sent]

    async def _fetch_reminders(self, telegram_ids: list[str]) -> list[dict]:
        if not self.secret or not telegram_ids:
            return []
        url = f"{self.site_url}/api/practice/reminders"
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url,
                headers={"x-practice-reminder-secret": self.secret, "content-type": "application/json"},
                json={"telegramIds": telegram_ids},
            ) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(f"ArtistYar reminder API returned {response.status}: {payload}")
                return payload.get("reminders") or []

    async def run_once(self) -> None:
        if not self.secret:
            logger.warning("ArtistYar reminder scheduler disabled: ARTISTYAR_PRACTICE_REMINDER_SECRET is not configured")
            return
        if not self._in_reminder_window():
            return

        db = SessionLocal()
        try:
            self._ensure_log_table(db)
            today = datetime.now(TEHRAN_TZ).date()
            ids = self._student_telegram_ids(db)
            ids = self._unsent_ids(db, ids, today)
            for offset in range(0, len(ids), 500):
                batch = ids[offset:offset + 500]
                reminders = await self._fetch_reminders(batch)
                for reminder in reminders:
                    telegram_id = str(reminder.get("telegramId") or "")
                    message = str(reminder.get("message") or "").strip()
                    if not telegram_id or not message:
                        continue
                    try:
                        await self.bot.send_message(chat_id=int(telegram_id), text=message)
                        db.execute(
                            text("""
                                insert into artistyar_practice_reminder_log (telegram_id, reminder_date)
                                values (:telegram_id, :reminder_date)
                                on conflict (telegram_id, reminder_date) do nothing
                            """),
                            {"telegram_id": telegram_id, "reminder_date": today},
                        )
                        db.commit()
                    except Exception:
                        db.rollback()
                        logger.exception("Failed to send ArtistYar practice reminder to %s", telegram_id)
        finally:
            db.close()
