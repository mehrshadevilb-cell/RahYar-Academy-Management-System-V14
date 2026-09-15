from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.user import User, UserRole
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import OnlineEnrollment, PaymentModel, EnrollmentStatus
from src.database.models.reservation import ReservationStatus
from src.database.models.attendance import AttendanceStatus
from src.services.reservation_service import ReservationService
from src.services.attendance_service import AttendanceService

# Import all models so foreign-key metadata is complete.
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


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _confirm_paid(reservation_service: ReservationService, db, reservation_id: int):
    """Payment gate: submit proof then admin-confirm."""
    reservation_service.submit_payment(db, reservation_id, proof="test-receipt")
    return reservation_service.confirm(db, reservation_id)


def test_duplicate_reservation_is_blocked():
    db = make_db()
    user = User(full_name="Ali", role=UserRole.STUDENT)
    db.add(user); db.commit(); db.refresh(user)
    course = OnlineCourse(name="Mixing", monthly_sessions=4, term_sessions=12)
    db.add(course); db.commit(); db.refresh(course)
    enrollment = OnlineEnrollment(user_id=user.id, online_course_id=course.id, payment_model=PaymentModel.MONTHLY, remaining_sessions=4)
    db.add(enrollment); db.commit(); db.refresh(enrollment)

    service = ReservationService()
    first = service.request_reservation(db, enrollment.id, "1405-01-01", "18:00")
    second = service.request_reservation(db, enrollment.id, "1405-01-01", "18:00")

    assert first is not None
    assert second is None


def test_present_consumes_once_and_cancel_does_not():
    db = make_db()
    user = User(full_name="Ali", role=UserRole.STUDENT)
    db.add(user); db.commit(); db.refresh(user)
    course = OnlineCourse(name="Mixing")
    db.add(course); db.commit(); db.refresh(course)
    enrollment = OnlineEnrollment(user_id=user.id, online_course_id=course.id, payment_model=PaymentModel.TERM, remaining_sessions=2)
    db.add(enrollment); db.commit(); db.refresh(enrollment)

    reservation_service = ReservationService()
    attendance_service = AttendanceService()

    cancelled = reservation_service.request_reservation(db, enrollment.id, "1405-01-02", "18:00")
    cancelled = _confirm_paid(reservation_service, db, cancelled.id)
    attendance_service.mark_attendance(db, enrollment, cancelled.requested_date, AttendanceStatus.CANCELLED, cancelled.id)
    db.refresh(enrollment)
    assert enrollment.remaining_sessions == 2
    assert enrollment.completed_sessions == 0

    present = reservation_service.request_reservation(db, enrollment.id, "1405-01-03", "18:00")
    present = _confirm_paid(reservation_service, db, present.id)
    attendance_service.mark_attendance(db, enrollment, present.requested_date, AttendanceStatus.PRESENT, present.id)
    attendance_service.mark_attendance(db, enrollment, present.requested_date, AttendanceStatus.PRESENT, present.id)
    db.refresh(enrollment)
    db.refresh(present)

    assert enrollment.remaining_sessions == 1
    assert enrollment.completed_sessions == 1
    assert present.status == ReservationStatus.COMPLETED


def test_last_present_ends_enrollment():
    db = make_db()
    user = User(full_name="Ali", role=UserRole.STUDENT)
    db.add(user); db.commit(); db.refresh(user)
    course = OnlineCourse(name="Piano")
    db.add(course); db.commit(); db.refresh(course)
    enrollment = OnlineEnrollment(user_id=user.id, online_course_id=course.id, payment_model=PaymentModel.TERM, remaining_sessions=1)
    db.add(enrollment); db.commit(); db.refresh(enrollment)

    reservation_service = ReservationService()
    reservation = reservation_service.request_reservation(db, enrollment.id, "1405-01-04", "19:00")
    reservation = _confirm_paid(reservation_service, db, reservation.id)
    AttendanceService().mark_attendance(db, enrollment, reservation.requested_date, AttendanceStatus.PRESENT, reservation.id)
    db.refresh(enrollment)

    assert enrollment.remaining_sessions == 0
    assert enrollment.status == EnrollmentStatus.ENDED
