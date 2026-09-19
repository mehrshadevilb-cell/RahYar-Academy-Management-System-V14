from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.discount_code import DiscountType
from src.services.discount_code_service import DiscountCodeService

# Import all models so foreign-key metadata is complete.
from src.database.models.user import User, UserRole
from src.database.models.course import Course
from src.database.models.enrollment import Enrollment
from src.database.models.payment import Payment
from src.database.models.payment_card import PaymentCard
from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.telegram_channel import TelegramChannel
from src.database.models.license import License
from src.database.models.invite_link import TelegramInviteLink
from src.database.models.telegram_account import TelegramAccount
from src.database.models.student_profile import StudentProfile
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import OnlineEnrollment
from src.database.models.reservation import Reservation
from src.database.models.attendance import Attendance
from src.database.models.installment import Installment


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_code_rejects_duplicate():
    db = make_db()
    service = DiscountCodeService()

    first = service.create_code(
        db, code="summer30", discount_type=DiscountType.PERCENTAGE,
        value=30, max_uses=None, expires_at=None,
    )
    assert first is not None
    assert first.code == "SUMMER30"  # normalized to upper-case

    duplicate = service.create_code(
        db, code="SUMMER30", discount_type=DiscountType.FIXED,
        value=10_000, max_uses=None, expires_at=None,
    )
    assert duplicate is None


def test_validate_percentage_discount_calculates_correct_amount():
    db = make_db()
    service = DiscountCodeService()

    service.create_code(
        db, code="TWENTY", discount_type=DiscountType.PERCENTAGE,
        value=20, max_uses=None, expires_at=None,
    )

    code, final_price, discount_amount, error = service.validate(db, "twenty", 100_000)

    assert error is None
    assert discount_amount == 20_000
    assert final_price == 80_000


def test_validate_fixed_discount_never_makes_price_negative():
    db = make_db()
    service = DiscountCodeService()

    service.create_code(
        db, code="BIGFIXED", discount_type=DiscountType.FIXED,
        value=500_000, max_uses=None, expires_at=None,
    )

    code, final_price, discount_amount, error = service.validate(db, "BIGFIXED", 100_000)

    assert error is None
    assert final_price == 0
    assert discount_amount == 100_000  # capped at the original price


def test_validate_rejects_inactive_code():
    db = make_db()
    service = DiscountCodeService()

    code = service.create_code(
        db, code="OFFCODE", discount_type=DiscountType.PERCENTAGE,
        value=10, max_uses=None, expires_at=None,
    )
    service.toggle_active(db, code.id)

    result_code, final_price, discount_amount, error = service.validate(db, "OFFCODE", 50_000)

    assert result_code is None
    assert error is not None
    assert final_price == 50_000
    assert discount_amount == 0


def test_validate_rejects_expired_code():
    db = make_db()
    service = DiscountCodeService()

    service.create_code(
        db, code="OLDCODE", discount_type=DiscountType.PERCENTAGE,
        value=10, max_uses=None,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    result_code, _, _, error = service.validate(db, "OLDCODE", 50_000)

    assert result_code is None
    assert error is not None


def test_reserve_and_release_usage_cycle_respects_max_uses():
    db = make_db()
    service = DiscountCodeService()

    code = service.create_code(
        db, code="ONLYONE", discount_type=DiscountType.PERCENTAGE,
        value=10, max_uses=1, expires_at=None,
    )

    # First redemption succeeds and reserves the only usage slot.
    result_code, _, _, error = service.validate(db, "ONLYONE", 100_000)
    assert error is None
    service.reserve_usage(db, result_code)

    # A second student trying the same code is correctly turned away.
    blocked_code, _, _, blocked_error = service.validate(db, "ONLYONE", 100_000)
    assert blocked_code is None
    assert blocked_error is not None

    # The first payment gets rejected by the owner -> usage is released.
    service.release_usage_by_id(db, code.id)

    # Now a new student can use the same code again.
    reused_code, _, _, reused_error = service.validate(db, "ONLYONE", 100_000)
    assert reused_error is None
    assert reused_code.id == code.id
