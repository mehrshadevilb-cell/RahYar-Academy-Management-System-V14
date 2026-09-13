from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.user import User, UserRole
from src.database.models.course import Course
from src.database.models.payment import Payment
from src.services.payment_service import PaymentService

# Import all models so foreign-key metadata is complete.
from src.database.models.telegram_account import TelegramAccount
from src.database.models.enrollment import Enrollment
from src.database.models.payment_card import PaymentCard
from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.telegram_channel import TelegramChannel
from src.database.models.license import License
from src.database.models.invite_link import TelegramInviteLink
from src.database.models.student_profile import StudentProfile
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import OnlineEnrollment
from src.database.models.reservation import Reservation
from src.database.models.attendance import Attendance
from src.database.models.installment import Installment
from src.database.models.discount_code import DiscountCode
from src.database.models.admin_log import AdminLog
from src.database.models.referral import Referral


# A realistic real-world Telegram user id: bigger than a 32-bit signed
# INTEGER's max (2,147,483,647). This is exactly the value that broke
# payment approval in production on Postgres.
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
    """approved_by_id stores the admin's raw Telegram id, not a
    users.id row - it must never be re-declared as a foreign key
    (that exact mistake is what broke payment approval in production)."""

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
