import csv
import io
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.user import User, UserRole
from src.database.models.course import Course, ProductDeliveryType
from src.database.models.payment import Payment
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import OnlineEnrollment, PaymentModel
from src.database.models.installment import Installment, InstallmentStatus
from src.services.report_service import ReportService

# Import all models so foreign-key metadata is complete.
from src.database.models.telegram_account import TelegramAccount
from src.database.models.student_profile import StudentProfile
from src.database.models.enrollment import Enrollment
from src.database.models.payment_card import PaymentCard
from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.telegram_channel import TelegramChannel
from src.database.models.license import License
from src.database.models.invite_link import TelegramInviteLink
from src.database.models.reservation import Reservation
from src.database.models.attendance import Attendance
from src.database.models.discount_code import DiscountCode
from src.database.models.admin_log import AdminLog


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def parse_csv(content: bytes):
    # utf-8-sig strips the BOM the export intentionally adds for Excel.
    text = content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def test_payments_report_includes_header_and_row():

    db = make_db()

    user = User(full_name="Sara", role=UserRole.STUDENT, phone="0912")
    db.add(user)
    db.commit()
    db.refresh(user)

    course = Course(title="Piano Basics", price=500_000, delivery_type=ProductDeliveryType.SPOTPLAYER)
    db.add(course)
    db.commit()
    db.refresh(course)

    payment = Payment(user_id=user.id, course_id=course.id, amount=500_000, status="approved")
    db.add(payment)
    db.commit()

    report = ReportService()
    rows = parse_csv(report.payments_report(db))

    assert rows[0][0] == "شناسه"
    assert len(rows) == 2
    assert rows[1][1] == "Sara"
    assert rows[1][3] == "Piano Basics"
    assert rows[1][4] == "500000"


def test_payments_report_filters_by_status():

    db = make_db()

    user = User(full_name="Ali", role=UserRole.STUDENT)
    db.add(user)
    db.commit()
    db.refresh(user)

    course = Course(title="Theory", price=100_000, delivery_type=ProductDeliveryType.SPOTPLAYER)
    db.add(course)
    db.commit()
    db.refresh(course)

    db.add(Payment(user_id=user.id, course_id=course.id, amount=100_000, status="pending"))
    db.add(Payment(user_id=user.id, course_id=course.id, amount=100_000, status="approved"))
    db.commit()

    report = ReportService()
    rows = parse_csv(report.payments_report(db, status="approved"))

    # header + exactly one approved payment
    assert len(rows) == 2
    assert rows[1][6] == "approved"


def test_students_report_only_includes_students_not_admins():

    db = make_db()

    db.add(User(full_name="Student One", role=UserRole.STUDENT))
    db.add(User(full_name="Owner Account", role=UserRole.ADMIN))
    db.commit()

    report = ReportService()
    rows = parse_csv(report.students_report(db))

    names = [row[1] for row in rows[1:]]
    assert "Student One" in names
    assert "Owner Account" not in names


def test_online_enrollments_report_reflects_remaining_sessions():

    db = make_db()

    user = User(full_name="Neda", role=UserRole.STUDENT)
    db.add(user)
    db.commit()
    db.refresh(user)

    course = OnlineCourse(name="Guitar", monthly_price=800_000)
    db.add(course)
    db.commit()
    db.refresh(course)

    enrollment = OnlineEnrollment(
        user_id=user.id,
        online_course_id=course.id,
        payment_model=PaymentModel.MONTHLY,
        remaining_sessions=3,
        completed_sessions=1,
    )
    db.add(enrollment)
    db.commit()

    report = ReportService()
    rows = parse_csv(report.online_enrollments_report(db))

    assert rows[1][1] == "Neda"
    assert rows[1][2] == "Guitar"
    assert rows[1][4] == "3"
    assert rows[1][5] == "1"


def test_installments_report_can_filter_by_status():

    db = make_db()

    user = User(full_name="Kian", role=UserRole.STUDENT)
    db.add(user)
    db.commit()
    db.refresh(user)

    course = OnlineCourse(name="Violin", monthly_price=1_000_000)
    db.add(course)
    db.commit()
    db.refresh(course)

    enrollment = OnlineEnrollment(
        user_id=user.id,
        online_course_id=course.id,
        payment_model=PaymentModel.MONTHLY,
        remaining_sessions=4,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    db.add(Installment(
        enrollment_id=enrollment.id, installment_number=1, amount=1_000_000,
        due_date=date(2026, 1, 1), status=InstallmentStatus.PAID, paid_date=date(2025, 12, 30),
    ))
    db.add(Installment(
        enrollment_id=enrollment.id, installment_number=2, amount=1_000_000,
        due_date=date(2026, 2, 1), status=InstallmentStatus.PENDING,
    ))
    db.commit()

    report = ReportService()
    rows = parse_csv(report.installments_report(db, status=InstallmentStatus.PENDING))

    assert len(rows) == 2
    assert rows[1][3] == "2"
    assert rows[1][7] == "pending"
