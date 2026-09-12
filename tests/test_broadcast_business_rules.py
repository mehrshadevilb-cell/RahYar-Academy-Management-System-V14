import asyncio

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.user import User, UserRole
from src.database.models.telegram_account import TelegramAccount
from src.services.broadcast_service import BroadcastService

# Import all models so foreign-key metadata is complete.
from src.database.models.course import Course
from src.database.models.enrollment import Enrollment
from src.database.models.payment import Payment
from src.database.models.payment_card import PaymentCard
from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.telegram_channel import TelegramChannel
from src.database.models.license import License
from src.database.models.invite_link import TelegramInviteLink
from src.database.models.student_profile import StudentProfile
from src.database.models.reservation import Reservation
from src.database.models.attendance import Attendance
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import OnlineEnrollment
from src.database.models.installment import Installment
from src.database.models.discount_code import DiscountCode


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_account(db, telegram_id: str):
    user = User(full_name=f"User {telegram_id}", role=UserRole.STUDENT)
    db.add(user)
    db.commit()
    db.refresh(user)

    account = TelegramAccount(user_id=user.id, telegram_id=telegram_id)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


class FakeBot:
    """
    Minimal stand-in for aiogram's Bot.copy_message with scripted
    per-chat_id outcomes, so the service's fan-out/error-handling logic
    can be tested without any network access or a real Telegram API.
    """

    def __init__(self, outcomes: dict[int, object]):
        # outcomes[chat_id] is either None (success), an exception
        # instance to raise, or a list of exceptions/None to raise in
        # sequence across repeated calls for that chat_id.
        self.outcomes = outcomes
        self.calls: list[int] = []

    async def copy_message(self, chat_id, from_chat_id, message_id):
        self.calls.append(chat_id)

        outcome = self.outcomes.get(chat_id)

        if isinstance(outcome, list):
            step = outcome.pop(0)
        else:
            step = outcome

        if step is None:
            return
        raise step


def test_broadcast_counts_success_blocked_and_failed():

    db = make_db()

    add_account(db, "1")
    add_account(db, "2")
    add_account(db, "3")

    bot = FakeBot(
        {
            1: None,
            2: TelegramForbiddenError(method=None, message="blocked"),
            3: TelegramAPIError(method=None, message="boom"),
        }
    )

    service = BroadcastService(delay_seconds=0)

    result = asyncio.run(
        service.send(bot=bot, db=db, from_chat_id=999, message_id=1)
    )

    assert result.total == 3
    assert result.sent == 1
    assert result.blocked == 1
    assert result.failed == 1


def test_broadcast_excludes_admin_chat():

    db = make_db()

    add_account(db, "1")
    admin_account = add_account(db, "999")

    bot = FakeBot({1: None})

    service = BroadcastService(delay_seconds=0)

    result = asyncio.run(
        service.send(
            bot=bot,
            db=db,
            from_chat_id=999,
            message_id=1,
            exclude_telegram_ids={admin_account.telegram_id},
        )
    )

    assert result.total == 1
    assert bot.calls == [1]


def test_broadcast_retries_once_after_flood_control_then_succeeds():

    db = make_db()
    add_account(db, "1")

    bot = FakeBot(
        {
            1: [
                TelegramRetryAfter(method=None, message="flood", retry_after=0),
                None,
            ]
        }
    )

    service = BroadcastService(delay_seconds=0)

    result = asyncio.run(
        service.send(bot=bot, db=db, from_chat_id=999, message_id=1)
    )

    assert result.sent == 1
    assert result.failed == 0
    assert bot.calls == [1, 1]


def test_broadcast_progress_callback_reports_final_total():

    db = make_db()
    for i in range(1, 4):
        add_account(db, str(i))

    bot = FakeBot({1: None, 2: None, 3: None})

    service = BroadcastService(delay_seconds=0)

    progress_calls = []

    async def on_progress(sent_so_far, total):
        progress_calls.append((sent_so_far, total))

    asyncio.run(
        service.send(
            bot=bot, db=db, from_chat_id=999, message_id=1, on_progress=on_progress
        )
    )

    # Only three accounts (< 20), so progress should fire exactly once,
    # on the final message, with the full total.
    assert progress_calls == [(3, 3)]
