import asyncio
import logging

from aiogram import Bot

from src.database.session import SessionLocal
from src.database.repositories.online_enrollment_repository import (
    OnlineEnrollmentRepository,
)
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.installment_service import InstallmentService
from src.core.config.settings import get_settings


logger = logging.getLogger(__name__)

# Reminder flags are date-based (not time-based), so re-running within the
# same day is always a no-op. A few hours between checks is enough to
# catch the day's due dates promptly without hammering the DB/Telegram.
DEFAULT_INTERVAL_SECONDS = 6 * 60 * 60

REMINDER_TEXT = {
    7: (
        "📅 یادآوری: ۷ روز تا سررسید قسط شماره {number} کلاس «{course}» "
        "شما باقی مانده.\n💳 مبلغ: {amount:,} تومان"
    ),
    3: (
        "📅 یادآوری: ۳ روز تا سررسید قسط شماره {number} کلاس «{course}» "
        "شما باقی مانده.\n💳 مبلغ: {amount:,} تومان"
    ),
    1: (
        "⏰ فردا سررسید قسط شماره {number} کلاس «{course}» شماست.\n"
        "💳 مبلغ: {amount:,} تومان"
    ),
    0: (
        "⏰ امروز سررسید قسط شماره {number} کلاس «{course}» شماست.\n"
        "💳 مبلغ: {amount:,} تومان\nلطفاً هرچه زودتر پرداخت را انجام دهید."
    ),
}

OVERDUE_TEXT = (
    "⚠️ قسط شماره {number} کلاس «{course}» شما ({amount:,} تومان) از "
    "سررسید گذشته است. لطفاً در اسرع وقت نسبت به پرداخت اقدام کنید."
)

OWNER_OVERDUE_TEXT = (
    "⚠️ {count} قسط تازه معوق شد. برای بررسی به «پنل مدیریت > اقساط» مراجعه کنید."
)


class InstallmentReminderScheduler:
    """
    Background loop for installment reminders (7/3/1 day-before + due-date)
    and overdue detection. Runs independently of Telegram update handling,
    so unlike the handlers it does not receive a `db` session from
    DatabaseMiddleware - it opens and closes its own session per cycle.

    Every notification this scheduler sends is guarded by a persisted flag
    or a status transition (see InstallmentService), so an interval that
    is too short, a process restart, or overlapping runs cannot produce
    duplicate messages.
    """

    def __init__(self, bot: Bot, interval_seconds: int = DEFAULT_INTERVAL_SECONDS):
        self.bot = bot
        self.interval_seconds = interval_seconds
        self.installment_service = InstallmentService()
        self.enrollment_repository = OnlineEnrollmentRepository()
        self.telegram_repository = TelegramRepository()
        self.settings = get_settings()
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
                await self.run_once()
            except Exception:
                logger.exception("Installment reminder cycle failed")
            await asyncio.sleep(self.interval_seconds)

    async def run_once(self) -> None:
        db = SessionLocal()
        try:
            await self._send_due_reminders(db)
            await self._handle_newly_overdue(db)
        finally:
            db.close()

    async def _send_due_reminders(self, db) -> None:
        for installment, offset in self.installment_service.get_reminder_batch(db):
            enrollment = self.enrollment_repository.get_by_id(db, installment.enrollment_id)
            if not enrollment:
                # Data integrity issue (orphaned installment) - don't send,
                # don't silently mark as sent; leave for manual inspection.
                logger.warning(
                    "Installment %s has no matching enrollment; skipping reminder",
                    installment.id,
                )
                continue

            await self._notify_student(
                db,
                enrollment,
                REMINDER_TEXT[offset].format(
                    number=installment.installment_number,
                    course=enrollment.online_course.name,
                    amount=installment.amount,
                ),
            )

            self.installment_service.mark_reminder_sent(db, installment, offset)

    async def _handle_newly_overdue(self, db) -> None:
        newly_overdue = self.installment_service.sync_overdue(db)

        if not newly_overdue:
            return

        for installment in newly_overdue:
            enrollment = self.enrollment_repository.get_by_id(db, installment.enrollment_id)
            if not enrollment:
                logger.warning(
                    "Installment %s has no matching enrollment; skipping overdue notice",
                    installment.id,
                )
                continue

            await self._notify_student(
                db,
                enrollment,
                OVERDUE_TEXT.format(
                    number=installment.installment_number,
                    course=enrollment.online_course.name,
                    amount=installment.amount,
                ),
            )

        if self.settings.OWNER_ID:
            try:
                await self.bot.send_message(
                    chat_id=self.settings.OWNER_ID,
                    text=OWNER_OVERDUE_TEXT.format(count=len(newly_overdue)),
                )
            except Exception:
                logger.exception("Failed to notify owner about overdue installments")

    async def _notify_student(self, db, enrollment, text: str) -> None:
        telegram_account = self.telegram_repository.get_by_user_id(db, enrollment.user_id)

        if not telegram_account:
            logger.warning(
                "User %s has no telegram account; skipping installment notification",
                enrollment.user_id,
            )
            return

        try:
            await self.bot.send_message(chat_id=telegram_account.telegram_id, text=text)
        except Exception:
            logger.exception(
                "Failed to send installment notification to user_id=%s", enrollment.user_id
            )
