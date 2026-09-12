from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.user import User, UserRole
from src.database.models.telegram_account import TelegramAccount
from src.database.models.referral import ReferralStatus
from src.database.models.discount_code import DiscountType

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
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import OnlineEnrollment
from src.database.models.reservation import Reservation
from src.database.models.attendance import Attendance
from src.database.models.installment import Installment
from src.database.models.discount_code import DiscountCode
from src.database.models.admin_log import AdminLog

from src.services.referral_service import ReferralService


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_user_with_telegram(db, full_name, telegram_id):
    user = User(full_name=full_name, role=UserRole.STUDENT)
    db.add(user)
    db.commit()
    db.refresh(user)

    account = TelegramAccount(user_id=user.id, telegram_id=telegram_id, username=None)
    db.add(account)
    db.commit()

    return user


def test_create_referral_if_eligible_creates_pending_referral():
    db = make_db()
    service = ReferralService()

    referrer = make_user_with_telegram(db, "Referrer", "1001")
    referred = make_user_with_telegram(db, "Referred", "2002")

    referral = service.create_referral_if_eligible(db, "1001", referred.id)

    assert referral is not None
    assert referral.referrer_id == referrer.id
    assert referral.referred_id == referred.id
    assert referral.status == ReferralStatus.PENDING


def test_create_referral_returns_none_for_unknown_referrer_code():
    db = make_db()
    service = ReferralService()

    referred = make_user_with_telegram(db, "Referred", "2002")

    referral = service.create_referral_if_eligible(db, "does-not-exist", referred.id)

    assert referral is None


def test_create_referral_rejects_self_referral():
    db = make_db()
    service = ReferralService()

    user = make_user_with_telegram(db, "Solo", "3003")

    referral = service.create_referral_if_eligible(db, "3003", user.id)

    assert referral is None


def test_create_referral_only_allowed_once_per_referred_user():
    db = make_db()
    service = ReferralService()

    referrer_a = make_user_with_telegram(db, "A", "1001")
    referrer_b = make_user_with_telegram(db, "B", "1002")
    referred = make_user_with_telegram(db, "Referred", "2002")

    first = service.create_referral_if_eligible(db, "1001", referred.id)
    second = service.create_referral_if_eligible(db, "1002", referred.id)

    assert first is not None
    assert second is None  # already referred by A - B's code doesn't override it


def test_reward_referrer_if_pending_issues_discount_code_and_flips_status():
    db = make_db()
    service = ReferralService()

    make_user_with_telegram(db, "Referrer", "1001")
    referred = make_user_with_telegram(db, "Referred", "2002")

    service.create_referral_if_eligible(db, "1001", referred.id)

    rewarded = service.reward_referrer_if_pending(db, referred.id)

    assert rewarded is not None
    assert rewarded.status == ReferralStatus.REWARDED
    assert rewarded.reward_discount_code_id is not None
    assert rewarded.rewarded_at is not None

    code = service.discount_code_service.get_by_id(db, rewarded.reward_discount_code_id)
    assert code.discount_type == DiscountType.PERCENTAGE
    assert code.max_uses == 1


def test_reward_referrer_if_pending_only_rewards_once():
    db = make_db()
    service = ReferralService()

    make_user_with_telegram(db, "Referrer", "1001")
    referred = make_user_with_telegram(db, "Referred", "2002")

    service.create_referral_if_eligible(db, "1001", referred.id)

    first_reward = service.reward_referrer_if_pending(db, referred.id)
    second_reward = service.reward_referrer_if_pending(db, referred.id)

    assert first_reward is not None
    assert second_reward is None


def test_reward_referrer_if_pending_returns_none_when_no_referral_exists():
    db = make_db()
    service = ReferralService()

    lone_user = make_user_with_telegram(db, "NoReferral", "9999")

    result = service.reward_referrer_if_pending(db, lone_user.id)

    assert result is None
