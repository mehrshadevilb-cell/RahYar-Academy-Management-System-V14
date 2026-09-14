from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from src.database.base import Base
from src.database.models.support_request import SupportStatus
from src.database.models.user import User, UserRole
from src.services.support_service import (
    MAX_OPEN_PER_USER,
    SupportService,
    SupportServiceError,
)


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_user(db, name="Student"):
    user = User(full_name=name, role=UserRole.STUDENT)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_and_reply_flow():
    db = make_db()
    service = SupportService()
    user = make_user(db)

    request = service.create_request(
        db, user_id=user.id, telegram_id="111", message="مشکل در پرداخت"
    )
    assert request.status == SupportStatus.OPEN

    answered = service.reply(db, request.id, "رسید شما بررسی شد")
    assert answered.status == SupportStatus.ANSWERED
    assert answered.admin_reply == "رسید شما بررسی شد"
    assert answered.answered_at is not None

    closed = service.close(db, request.id)
    assert closed.status == SupportStatus.CLOSED
    assert closed.closed_at is not None


def test_rejects_empty_and_too_many_open():
    db = make_db()
    service = SupportService()
    user = make_user(db)

    with pytest.raises(SupportServiceError, match="empty_message"):
        service.create_request(db, user_id=user.id, telegram_id="1", message="  ")

    for i in range(MAX_OPEN_PER_USER):
        service.create_request(
            db, user_id=user.id, telegram_id="1", message=f"msg {i}"
        )

    with pytest.raises(SupportServiceError, match="too_many_open"):
        service.create_request(db, user_id=user.id, telegram_id="1", message="extra")


def test_cannot_reply_closed():
    db = make_db()
    service = SupportService()
    user = make_user(db)
    request = service.create_request(
        db, user_id=user.id, telegram_id="1", message="help"
    )
    service.close(db, request.id)

    with pytest.raises(SupportServiceError, match="already_closed"):
        service.reply(db, request.id, "late reply")
