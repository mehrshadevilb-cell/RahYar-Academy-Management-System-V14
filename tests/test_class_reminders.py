from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.utils.jalali import format_jalali_date, gregorian_to_jalali
from src.database.base import Base
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import (
    EnrollmentStatus,
    OnlineEnrollment,
    PaymentModel,
)
from src.database.models.reservation import Reservation, ReservationStatus
from src.database.models.telegram_account import TelegramAccount
from src.database.models.user import User, UserRole
from src.database.models.discount_code import DiscountCode
from src.database.models.course import Course
from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.payment import Payment
from src.database.models.student_profile import StudentProfile
from src.database.models.telegram_channel import TelegramChannel
from src.database.models.license import License
from src.database.models.invite_link import TelegramInviteLink
from src.database.models.attendance import Attendance
from src.database.models.installment import Installment
from src.services.reminder_scheduler import InstallmentReminderScheduler, _class_start_in_tehran, should_send_one_hour_reminder, TEHRAN_TZ


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def jalali_for(d: date) -> str:
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return format_jalali_date(jy, jm, jd)


def test_one_hour_reminder_window_is_timezone_aware_and_bounded():
    start = _class_start_in_tehran("1405-06-24", "18:30")
    assert start is not None
    assert start.tzinfo == TEHRAN_TZ
    assert should_send_one_hour_reminder(start, start - timedelta(minutes=30)) is True
    assert should_send_one_hour_reminder(start, start - timedelta(hours=2)) is False
    assert should_send_one_hour_reminder(start, start + timedelta(minutes=1)) is False


@pytest.mark.asyncio
async def test_class_reminder_same_day_and_idempotent(monkeypatch):
    db = make_db()
    user = User(full_name="Student", role=UserRole.STUDENT)
    course = OnlineCourse(name="Piano", teacher="T", duration_minutes=60)
    db.add_all([user, course])
    db.commit()
    db.refresh(user)
    db.refresh(course)

    db.add(TelegramAccount(user_id=user.id, telegram_id="999001"))
    enrollment = OnlineEnrollment(
        user_id=user.id,
        online_course_id=course.id,
        payment_model=PaymentModel.MONTHLY,
        remaining_sessions=4,
        status=EnrollmentStatus.ACTIVE,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    today_j = jalali_for(date.today())
    reservation = Reservation(
        enrollment_id=enrollment.id,
        requested_date=today_j,
        requested_time="18:30",
        status=ReservationStatus.CONFIRMED,
        reminder_1d_sent=False,
        reminder_due_sent=False,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    bot = MagicMock()
    bot.send_message = AsyncMock()

    scheduler = InstallmentReminderScheduler(bot)

    async def run_with_db():
        await scheduler._send_class_reminders(db)

    await run_with_db()
    assert reservation.reminder_due_sent is True
    assert bot.send_message.await_count == 1

    await run_with_db()
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_class_reminder_tomorrow():
    db = make_db()
    user = User(full_name="Student", role=UserRole.STUDENT)
    course = OnlineCourse(name="Mixing", teacher="T", duration_minutes=60)
    db.add_all([user, course])
    db.commit()
    db.refresh(user)
    db.refresh(course)
    db.add(TelegramAccount(user_id=user.id, telegram_id="999002"))
    enrollment = OnlineEnrollment(
        user_id=user.id,
        online_course_id=course.id,
        payment_model=PaymentModel.MONTHLY,
        remaining_sessions=4,
        status=EnrollmentStatus.ACTIVE,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    tomorrow_j = jalali_for(date.today() + timedelta(days=1))
    reservation = Reservation(
        enrollment_id=enrollment.id,
        requested_date=tomorrow_j,
        requested_time="10:00",
        status=ReservationStatus.CONFIRMED,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    bot = MagicMock()
    bot.send_message = AsyncMock()
    scheduler = InstallmentReminderScheduler(bot)

    await scheduler._send_class_reminders(db)
    assert reservation.reminder_1d_sent is True
    assert bot.send_message.await_count == 1
