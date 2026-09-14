import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.user import User, UserRole
from src.database.models.course import Course
from src.database.models.payment import Payment
from src.services.payment_service import PaymentReviewError, PaymentService

from src.database.models.telegram_account import TelegramAccount  # noqa: F401
from src.database.models.enrollment import Enrollment  # noqa: F401
from src.database.models.payment_card import PaymentCard  # noqa: F401
from src.database.models.spotplayer_course import SpotPlayerCourse  # noqa: F401
from src.database.models.telegram_channel import TelegramChannel  # noqa: F401
from src.database.models.license import License  # noqa: F401
from src.database.models.invite_link import TelegramInviteLink  # noqa: F401
from src.database.models.student_profile import StudentProfile  # noqa: F401
from src.database.models.online_course import OnlineCourse  # noqa: F401
from src.database.models.online_enrollment import OnlineEnrollment  # noqa: F401
from src.database.models.reservation import Reservation  # noqa: F401
from src.database.models.attendance import Attendance  # noqa: F401
from src.database.models.installment import Installment  # noqa: F401
from src.database.models.discount_code import DiscountCode  # noqa: F401
from src.database.models.admin_log import AdminLog  # noqa: F401
from src.database.models.referral import Referral  # noqa: F401

REALISTIC_LARGE_TELEGRAM_ID = 8234306902


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_pending_payment(db):
    user = User(full_name="Student", role=UserRole.STUDENT)
    db.add(user)
    db.commit()
    db.refresh(user)

    course = Course(title="Test Course", price=1_000_000, is_active=True)
    db.add(course)
    db.commit()
    db.refresh(course)

    payment = Payment(
        user_id=user.id,
        course_id=course.id,
        amount=course.price,
        status="pending",
        receipt_file_id="dummy-file-id",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def test_approved_by_id_column_has_no_foreign_key():
    column = Payment.__table__.c.approved_by_id
    assert len(column.foreign_keys) == 0


def test_approve_accepts_a_telegram_id_larger_than_32_bit_int():
    db = make_db()
    service = PaymentService()
    payment = make_pending_payment(db)

    approved = service.approve(
        db=db,
        payment_id=payment.id,
        admin_telegram_id=REALISTIC_LARGE_TELEGRAM_ID,
    )

    assert approved.status == "approved"
    assert approved.approved_by_id == REALISTIC_LARGE_TELEGRAM_ID


def test_reject_accepts_a_telegram_id_larger_than_32_bit_int():
    db = make_db()
    service = PaymentService()
    payment = make_pending_payment(db)

    rejected = service.reject(
        db=db,
        payment_id=payment.id,
        admin_telegram_id=REALISTIC_LARGE_TELEGRAM_ID,
        reason="test rejection",
    )

    assert rejected.status == "rejected"
    assert rejected.approved_by_id == REALISTIC_LARGE_TELEGRAM_ID


def test_approve_is_idempotent_when_already_approved():
    db = make_db()
    service = PaymentService()
    payment = make_pending_payment(db)

    first = service.approve(db, payment.id, REALISTIC_LARGE_TELEGRAM_ID)
    second = service.approve(db, payment.id, 111)

    assert first.status == "approved"
    assert second.status == "approved"
    # First reviewer wins; second call must not overwrite reviewer id.
    assert second.approved_by_id == REALISTIC_LARGE_TELEGRAM_ID


def test_cannot_approve_after_reject():
    db = make_db()
    service = PaymentService()
    payment = make_pending_payment(db)

    service.reject(db, payment.id, REALISTIC_LARGE_TELEGRAM_ID, reason="no")

    with pytest.raises(PaymentReviewError):
        service.approve(db, payment.id, REALISTIC_LARGE_TELEGRAM_ID)


def test_cannot_reject_after_approve():
    db = make_db()
    service = PaymentService()
    payment = make_pending_payment(db)

    service.approve(db, payment.id, REALISTIC_LARGE_TELEGRAM_ID)

    with pytest.raises(PaymentReviewError):
        service.reject(db, payment.id, REALISTIC_LARGE_TELEGRAM_ID, reason="late")
