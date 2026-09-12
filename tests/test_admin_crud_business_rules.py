import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.course import Course, ProductDeliveryType
from src.database.models.online_course import OnlineCourse
from src.services.online_course_service import OnlineCourseService
from src.services.product_integration_service import ProductIntegrationService

# Import all models so foreign-key metadata is complete.
from src.database.models.user import User, UserRole
from src.database.models.enrollment import Enrollment
from src.database.models.payment import Payment
from src.database.models.payment_card import PaymentCard
from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.telegram_channel import TelegramChannel
from src.database.models.license import License
from src.database.models.invite_link import TelegramInviteLink
from src.database.models.telegram_account import TelegramAccount
from src.database.models.student_profile import StudentProfile
from src.database.models.online_enrollment import OnlineEnrollment
from src.database.models.reservation import Reservation
from src.database.models.attendance import Attendance
from src.database.models.installment import Installment


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_online_course_create_and_field_edit():
    db = make_db()
    service = OnlineCourseService()

    course = service.create_course(
        db,
        name="Piano",
        teacher="Ali",
        duration_minutes=45,
        monthly_price=1_000_000,
        term_price=None,
        monthly_sessions=4,
        term_sessions=12,
    )

    updated = service.update_field(db, course.id, "monthly_price", "1500000")

    assert updated.monthly_price == 1_500_000
    # untouched fields survive the update
    assert updated.name == "Piano"
    assert updated.teacher == "Ali"


def test_online_course_update_rejects_unknown_field():
    db = make_db()
    service = OnlineCourseService()
    course = service.create_course(
        db, name="Piano", teacher=None, duration_minutes=45,
        monthly_price=None, term_price=None, monthly_sessions=4, term_sessions=12,
    )

    with pytest.raises(ValueError):
        service.update_field(db, course.id, "id", "999")


def test_online_course_toggle_active_does_not_affect_existing_enrollment_counts():
    db = make_db()
    service = OnlineCourseService()
    course = service.create_course(
        db, name="Piano", teacher=None, duration_minutes=45,
        monthly_price=None, term_price=None, monthly_sessions=4, term_sessions=12,
    )

    user = User(full_name="Student", role=UserRole.STUDENT)
    db.add(user)
    db.commit()
    db.refresh(user)

    from src.database.models.online_enrollment import PaymentModel
    enrollment = OnlineEnrollment(
        user_id=user.id,
        online_course_id=course.id,
        payment_model=PaymentModel.TERM,
        remaining_sessions=12,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    # Admin later changes the template's term_sessions to 20 and deactivates it.
    service.update_field(db, course.id, "term_sessions", "20")
    service.toggle_active(db, course.id)

    db.refresh(enrollment)
    # The already-enrolled student keeps their originally granted count.
    assert enrollment.remaining_sessions == 12


def test_product_integration_toggle_is_read_by_delivery_flows():
    db = make_db()
    product = Course(title="RahYar", delivery_type=ProductDeliveryType.SPOTPLAYER)
    db.add(product)
    db.commit()
    db.refresh(product)

    service = ProductIntegrationService()
    record = service.add_spotplayer_course(db, product.id, "sp_course_1", "Level 1")

    db.refresh(product)
    enabled_ids = [c.spotplayer_course_id for c in product.spotplayer_courses if c.enabled]
    assert enabled_ids == ["sp_course_1"]

    service.toggle_spotplayer_course(db, record.id)
    db.refresh(product)
    enabled_ids = [c.spotplayer_course_id for c in product.spotplayer_courses if c.enabled]
    assert enabled_ids == []
