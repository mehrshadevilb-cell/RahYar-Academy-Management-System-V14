from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.user import User, UserRole
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import OnlineEnrollment, PaymentModel
from src.database.models.installment import Installment, InstallmentStatus
from src.services.installment_service import InstallmentService

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
from src.database.models.reservation import Reservation
from src.database.models.attendance import Attendance


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_enrollment(db, due_date, status=InstallmentStatus.PENDING, number=1):
    user = User(full_name="Ali", role=UserRole.STUDENT)
    db.add(user)
    db.commit()
    db.refresh(user)

    course = OnlineCourse(name="Piano", monthly_price=1_000_000)
    db.add(course)
    db.commit()
    db.refresh(course)

    enrollment = OnlineEnrollment(
        user_id=user.id,
        online_course_id=course.id,
        payment_model=PaymentModel.MONTHLY,
        remaining_sessions=4,
        current_installment_number=number,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    installment = Installment(
        enrollment_id=enrollment.id,
        installment_number=number,
        amount=1_000_000,
        due_date=due_date,
        status=status,
    )
    db.add(installment)
    db.commit()
    db.refresh(installment)

    return enrollment, installment


def test_mark_paid_is_idempotent():
    db = make_db()
    _, installment = make_enrollment(db, date.today())
    service = InstallmentService()

    first = service.mark_paid(db, installment)
    paid_date_after_first = first.paid_date

    # Re-confirming (e.g. a Telegram double-click) must not change anything.
    second = service.mark_paid(db, installment)

    assert second.status == InstallmentStatus.PAID
    assert second.paid_date == paid_date_after_first


def test_reminder_batch_only_returns_matching_offset_and_only_once():
    db = make_db()
    _, due_in_3 = make_enrollment(db, date.today() + timedelta(days=3))

    service = InstallmentService()
    batch = service.get_reminder_batch(db)

    assert len(batch) == 1
    installment, offset = batch[0]
    assert installment.id == due_in_3.id
    assert offset == 3

    service.mark_reminder_sent(db, installment, offset)
    db.refresh(installment)
    assert installment.reminder_3d_sent is True

    # Running again the same day must not re-select it.
    batch_again = service.get_reminder_batch(db)
    assert batch_again == []


def test_reminder_batch_ignores_paid_and_overdue_installments():
    db = make_db()
    make_enrollment(db, date.today(), status=InstallmentStatus.PAID)
    make_enrollment(db, date.today() - timedelta(days=1), status=InstallmentStatus.OVERDUE)

    service = InstallmentService()
    assert service.get_reminder_batch(db) == []


def test_sync_overdue_transitions_past_due_pending_once():
    db = make_db()
    _, overdue_installment = make_enrollment(db, date.today() - timedelta(days=1))

    service = InstallmentService()
    newly_overdue = service.sync_overdue(db)

    assert len(newly_overdue) == 1
    assert newly_overdue[0].id == overdue_installment.id
    db.refresh(overdue_installment)
    assert overdue_installment.status == InstallmentStatus.OVERDUE

    # Second call must not report it again - it's no longer PENDING.
    assert service.sync_overdue(db) == []


def test_sync_overdue_does_not_touch_future_or_due_today_installments():
    db = make_db()
    _, due_today = make_enrollment(db, date.today())
    _, due_future = make_enrollment(db, date.today() + timedelta(days=7), number=1)

    service = InstallmentService()
    assert service.sync_overdue(db) == []

    db.refresh(due_today)
    db.refresh(due_future)
    assert due_today.status == InstallmentStatus.PENDING
    assert due_future.status == InstallmentStatus.PENDING
