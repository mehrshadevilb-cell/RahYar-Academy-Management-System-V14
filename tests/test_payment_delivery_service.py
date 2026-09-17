import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.course import Course, ProductDeliveryType
from src.database.models.license import License
from src.database.models.payment import Payment
from src.database.models.user import User, UserRole
from src.services.enrollment_service import EnrollmentService
from src.services.payment_delivery_service import PaymentDeliveryService

# Register all related tables for SQLite test metadata.
from src.database.models.enrollment import Enrollment  # noqa: F401
from src.database.models.invite_link import TelegramInviteLink  # noqa: F401
from src.database.models.spotplayer_course import SpotPlayerCourse  # noqa: F401
from src.database.models.telegram_account import TelegramAccount  # noqa: F401
from src.database.models.telegram_channel import TelegramChannel  # noqa: F401


class FakeLicenseService:
    def __init__(self) -> None:
        self.calls = 0

    async def issue_license(self, **kwargs):
        self.calls += 1
        return License(
            id=101,
            user_id=kwargs["user_id"],
            product_id=kwargs["product"].id,
            payment_id=kwargs["payment_id"],
            status="active",
            license_key="test-license",
            license_url="https://spotplayer.example/license",
        )


class FakeArtistYarService:
    def __init__(self) -> None:
        self.calls = 0

    async def deliver_channels(self, **kwargs):
        self.calls += 1
        return [{"channel_name": "ArtistYar", "invite_link": "https://t.me/+test", "error": None}]


class NoReferralService:
    def reward_referrer_if_pending(self, db, user_id):
        return None


class NoTelegramRepository:
    def get_by_user_id(self, db, user_id):
        return None


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_pending_payment(db, delivery_type):
    user = User(full_name="هنرجوی تست", phone="09121234567", role=UserRole.STUDENT)
    course = Course(title="دوره تست", price=1_000_000, is_active=True, delivery_type=delivery_type)
    db.add_all([user, course])
    db.commit()
    payment = Payment(user_id=user.id, course_id=course.id, amount=course.price, status="pending", receipt_file_id="receipt")
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def test_web_and_bot_can_share_spotplayer_delivery_idempotently():
    db = make_db()
    payment = make_pending_payment(db, ProductDeliveryType.SPOTPLAYER)
    licenses = FakeLicenseService()
    service = PaymentDeliveryService(
        enrollment_service=EnrollmentService(),
        license_service=licenses,
        artistyar_service=FakeArtistYarService(),
        referral_service=NoReferralService(),
        telegram_repository=NoTelegramRepository(),
    )

    first = asyncio.run(service.approve_and_deliver(db, payment_id=payment.id, admin_telegram_id=123, bot=None))
    second = asyncio.run(service.approve_and_deliver(db, payment_id=payment.id, admin_telegram_id=456, bot=None))

    assert first is not None
    assert first.payment.status == "approved"
    assert first.license is not None and first.license.license_key == "test-license"
    assert second is not None
    assert db.query(Enrollment).filter(Enrollment.user_id == payment.user_id, Enrollment.course_id == payment.course_id).count() == 1
    assert licenses.calls == 2  # Real LicenseService reuses the same active record on retry.


def test_telegram_product_creates_links_even_before_student_links_bot():
    db = make_db()
    payment = make_pending_payment(db, ProductDeliveryType.TELEGRAM)
    artistyar = FakeArtistYarService()
    service = PaymentDeliveryService(
        enrollment_service=EnrollmentService(),
        license_service=FakeLicenseService(),
        artistyar_service=artistyar,
        referral_service=NoReferralService(),
        telegram_repository=NoTelegramRepository(),
    )

    result = asyncio.run(service.approve_and_deliver(db, payment_id=payment.id, admin_telegram_id=123, bot=object()))

    assert result is not None
    assert artistyar.calls == 1
    assert result.channel_deliveries[0].invite_link == "https://t.me/+test"
    assert result.student_notified is False
    assert "student_telegram_not_linked" in result.warnings


def test_shared_delivery_preserves_existing_enrollment_on_repeat_approval():
    db = make_db()
    payment = make_pending_payment(db, ProductDeliveryType.SPOTPLAYER)
    enrollment = EnrollmentService().create_enrollment(
        db,
        user_id=payment.user_id,
        course_id=payment.course_id,
    )
    service = PaymentDeliveryService(
        enrollment_service=EnrollmentService(),
        license_service=FakeLicenseService(),
        artistyar_service=FakeArtistYarService(),
        referral_service=NoReferralService(),
        telegram_repository=NoTelegramRepository(),
    )

    result = asyncio.run(service.approve_and_deliver(db, payment_id=payment.id, admin_telegram_id=123))

    assert result is not None
    assert result.enrollment_id == enrollment.id
    assert db.query(Enrollment).filter(Enrollment.user_id == payment.user_id).count() == 1


def test_retrying_approved_delivery_does_not_reward_referral_twice():
    db = make_db()
    payment = make_pending_payment(db, ProductDeliveryType.SPOTPLAYER)
    service = PaymentDeliveryService(
        enrollment_service=EnrollmentService(),
        license_service=FakeLicenseService(),
        artistyar_service=FakeArtistYarService(),
        referral_service=NoReferralService(),
        telegram_repository=NoTelegramRepository(),
    )
    initial = asyncio.run(service.approve_and_deliver(db, payment_id=payment.id, admin_telegram_id=123))

    retried = asyncio.run(
        service.deliver_approved_payment(
            db,
            payment=initial.payment,
            notify_student=False,
            reward_referral=False,
        )
    )

    assert retried.referral_rewarded is None
    assert retried.license is not None
