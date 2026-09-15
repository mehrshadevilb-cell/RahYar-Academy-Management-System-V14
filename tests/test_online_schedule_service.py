from datetime import date

from src.database.models.online_time_slot import OnlineTimeSlot
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import OnlineEnrollment, PaymentModel
from src.database.models.user import User, UserRole
from src.database.models.reservation import ReservationStatus
from src.database.models.attendance import AttendanceStatus
from src.database.models.discount_code import DiscountCode
from src.services.online_schedule_service import OnlineScheduleService
from src.services.reservation_service import ReservationService
from src.services.attendance_service import AttendanceService

from tests.test_online_business_rules import make_db


def test_term_and_monthly_slot_plans_use_expected_counts():
    db = make_db()
    user = User(full_name="Student", role=UserRole.STUDENT)
    course = OnlineCourse(name="Mix", monthly_sessions=4, term_sessions=12)
    db.add_all([user, course]); db.commit(); db.refresh(user); db.refresh(course)
    slot = OnlineTimeSlot(online_course_id=course.id, weekday=5, start_time="15:00", end_time="15:30")
    db.add(slot); db.commit(); db.refresh(slot)
    term = OnlineEnrollment(user_id=user.id, online_course_id=course.id, payment_model=PaymentModel.TERM, remaining_sessions=12)
    db.add(term); db.commit(); db.refresh(term)

    plan = OnlineScheduleService().create_reservation_plan(db, term, slot.id, date(2026, 9, 19), 12)
    assert len(plan) == 12
    assert plan[0].status == ReservationStatus.WAITING_PAYMENT
    assert len({item.requested_date for item in plan}) == 12


def test_first_absence_creates_extension_and_second_consumes_session():
    db = make_db()
    user = User(full_name="Student", role=UserRole.STUDENT)
    course = OnlineCourse(name="Mix")
    db.add_all([user, course]); db.commit(); db.refresh(user); db.refresh(course)
    enrollment = OnlineEnrollment(user_id=user.id, online_course_id=course.id, payment_model=PaymentModel.TERM, remaining_sessions=3)
    db.add(enrollment); db.commit(); db.refresh(enrollment)
    service = ReservationService()
    first = service.request_reservation(db, enrollment.id, "2026-09-19", "15:00")
    service.submit_payment(db, first.id, "receipt"); service.confirm(db, first.id)
    AttendanceService().mark_attendance(db, enrollment, first.requested_date, AttendanceStatus.ABSENT, first.id)
    db.refresh(enrollment)
    assert enrollment.remaining_sessions == 3
    assert db.query(OnlineTimeSlot).count() == 0

    second = service.request_reservation(db, enrollment.id, "2026-10-03", "15:00")
    service.submit_payment(db, second.id, "receipt"); service.confirm(db, second.id)
    AttendanceService().mark_attendance(db, enrollment, second.requested_date, AttendanceStatus.ABSENT, second.id)
    db.refresh(enrollment)
    assert enrollment.remaining_sessions == 2
    assert enrollment.completed_sessions == 1
