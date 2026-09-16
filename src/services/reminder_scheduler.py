import asyncio
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

from src.core.config.settings import get_settings
from src.core.utils.jalali import format_jalali_date, gregorian_to_jalali, jalali_to_gregorian
from src.database.models.reservation import ReservationStatus
from src.database.repositories.online_enrollment_repository import (
    OnlineEnrollmentRepository,
)
from src.database.repositories.reservation_repository import ReservationRepository
from src.database.repositories.telegram_repository import TelegramRepository
from src.database.session import SessionLocal
from src.services.installment_service import InstallmentService
from src.services.notification_preference_service import NotificationPreferenceService

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 15 * 60
TEHRAN_TZ = ZoneInfo("Asia/Tehran")

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

CLASS_REMINDER_1D = (
    "📅 یادآوری کلاس\n\n"
    "فردا کلاس «{course}» شما در ساعت {time} برگزار می‌شود.\n"
    "تاریخ: {date}"
)

CLASS_REMINDER_DUE = (
    "⏰ امروز کلاس دارید\n\n"
    "کلاس «{course}» امروز ساعت {time} برگزار می‌شود.\n"
    "تاریخ: {date}\n"
    "لطفاً به‌موقع حاضر باشید."
)

CLASS_REMINDER_1H = (
    "⏳ یادآوری نزدیک شدن کلاس\n\n"
    "کلاس «{course}» شما حدود یک ساعت دیگر، ساعت {time} شروع می‌شود.\n"
    "تاریخ: {date}"
)


def _jalali_str_for_gregorian(d: date) -> str:
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return format_jalali_date(jy, jm, jd)


def _class_start_in_tehran(requested_date: str, requested_time: str) -> datetime | None:
    try:
        jy, jm, jd = (int(part) for part in requested_date.split("-"))
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        hour, minute = (int(part) for part in requested_time.split(":")[:2])
        return datetime(gy, gm, gd, hour, minute, tzinfo=TEHRAN_TZ)
    except (TypeError, ValueError):
        return None


def should_send_one_hour_reminder(class_start: datetime, now: datetime) -> bool:
    remaining = class_start - now
    return timedelta(0) <= remaining <= timedelta(hours=1)


class InstallmentReminderScheduler:
    """Background loop for installment + class reminders. Respects user mute prefs."""

    def __init__(self, bot: Bot, interval_seconds: int = DEFAULT_INTERVAL_SECONDS):
        self.bot = bot
        self.interval_seconds = interval_seconds
        self.installment_service = InstallmentService()
        self.enrollment_repository = OnlineEnrollmentRepository()
        self.reservation_repository = ReservationRepository()
        self.telegram_repository = TelegramRepository()
        self.pref_service = NotificationPreferenceService()
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
                logger.exception("Reminder cycle failed")
            await asyncio.sleep(self.interval_seconds)

    async def run_once(self) -> None:
        db = SessionLocal()
        try:
            await self._send_due_reminders(db)
            await self._handle_newly_overdue(db)
            await self._send_class_reminders(db)
        finally:
            db.close()

    async def _send_due_reminders(self, db) -> None:
        for installment, offset in self.installment_service.get_reminder_batch(db):
            enrollment = self.enrollment_repository.get_by_id(db, installment.enrollment_id)
            if not enrollment:
                continue
            if not self.pref_service.is_enabled(db, enrollment.user_id, "installment_reminders"):
                self.installment_service.mark_reminder_sent(db, installment, offset)
                continue
            await self._notify_student(
                db,
                enrollment.user_id,
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
                continue
            if not self.pref_service.is_enabled(db, enrollment.user_id, "installment_reminders"):
                continue
            await self._notify_student(
                db,
                enrollment.user_id,
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

    async def _send_class_reminders(self, db) -> None:
        try:
            today = date.today()
            today_j = _jalali_str_for_gregorian(today)
            tomorrow_j = _jalali_str_for_gregorian(today + timedelta(days=1))
            confirmed = self.reservation_repository.get_confirmed_upcoming(db)
        except (ProgrammingError, SQLAlchemyError):
            logger.exception("Class reminder query failed")
            try:
                db.rollback()
            except Exception:
                pass
            return

        for reservation in confirmed:
            if reservation.status != ReservationStatus.CONFIRMED:
                continue
            enrollment = self.enrollment_repository.get_by_id(db, reservation.enrollment_id)
            if not enrollment or not enrollment.online_course:
                continue
            if not self.pref_service.is_enabled(db, enrollment.user_id, "class_reminders"):
                # Still mark flags so we do not re-check forever when muted.
                if not reservation.reminder_1h_sent:
                    reservation.reminder_1h_sent = True
                if not reservation.reminder_1d_sent:
                    reservation.reminder_1d_sent = True
                if not reservation.reminder_due_sent:
                    reservation.reminder_due_sent = True
                db.commit()
                continue

            course_name = enrollment.online_course.name
            payload = {
                "course": course_name,
                "time": reservation.requested_time,
                "date": reservation.requested_date,
            }
            class_start = _class_start_in_tehran(reservation.requested_date, reservation.requested_time)
            now = datetime.now(TEHRAN_TZ)
            if (
                class_start is not None
                and should_send_one_hour_reminder(class_start, now)
                and not reservation.reminder_1h_sent
            ):
                await self._notify_student(db, enrollment.user_id, CLASS_REMINDER_1H.format(**payload))
                reservation.reminder_1h_sent = True
                db.commit()
            if reservation.requested_date == tomorrow_j and not reservation.reminder_1d_sent:
                await self._notify_student(db, enrollment.user_id, CLASS_REMINDER_1D.format(**payload))
                reservation.reminder_1d_sent = True
                db.commit()
            if reservation.requested_date == today_j and not reservation.reminder_due_sent:
                await self._notify_student(db, enrollment.user_id, CLASS_REMINDER_DUE.format(**payload))
                reservation.reminder_due_sent = True
                db.commit()

    async def _notify_student(self, db, user_id: int, text: str) -> None:
        telegram_account = self.telegram_repository.get_by_user_id(db, user_id)
        if not telegram_account:
            return
        try:
            await self.bot.send_message(chat_id=int(telegram_account.telegram_id), text=text)
        except Exception:
            logger.exception("Failed to send notification to user_id=%s", user_id)
