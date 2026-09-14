from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.models.course import Course
from src.database.models.installment import Installment, InstallmentStatus
from src.database.models.license import License
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import (
    EnrollmentStatus,
    OnlineEnrollment,
    PaymentModel,
)
from src.database.models.user import User, UserRole
from src.services.progress_service import ProgressService


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_progress_snapshot_and_format():
    db = make_db()
    user = User(full_name="Ali", role=UserRole.STUDENT)
    online = OnlineCourse(name="Mixing", teacher="T", duration_minutes=60, monthly_price=1000)
    product = Course(title="RahYar Pack", price=1000000, is_active=True)
    db.add_all([user, online, product])
    db.commit()
    db.refresh(user)
    db.refresh(online)
    db.refresh(product)

    enrollment = OnlineEnrollment(
        user_id=user.id,
        online_course_id=online.id,
        payment_model=PaymentModel.MONTHLY,
        remaining_sessions=2,
        completed_sessions=2,
        status=EnrollmentStatus.ACTIVE,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    db.add(
        Installment(
            enrollment_id=enrollment.id,
            installment_number=1,
            amount=1000,
            due_date=date.today(),
            status=InstallmentStatus.PENDING,
        )
    )
    db.add(
        License(
            user_id=user.id,
            product_id=product.id,
            status="active",
        )
    )
    db.commit()

    service = ProgressService()
    snap = service.get_snapshot(db, user.id)
    assert len(snap.online_enrollments) == 1
    assert len(snap.licenses) == 1
    assert len(snap.installments) == 1

    text = service.format_persian(snap)
    assert "Mixing" in text
    assert "RahYar Pack" in text
    assert "قسط" in text
