from sqlalchemy.orm import Session

from src.database.models.online_enrollment import (
    EnrollmentStatus,
    OnlineEnrollment,
    PaymentModel,
)
from src.database.repositories.online_enrollment_repository import (
    OnlineEnrollmentRepository,
)
from src.services.installment_service import InstallmentService


def sessions_for_plan(online_course, payment_model: PaymentModel) -> int:
    if payment_model == PaymentModel.WEEKLY:
        return 1
    if payment_model == PaymentModel.MONTHLY:
        return online_course.monthly_sessions or 4
    return online_course.term_sessions or 12


def cycle_amount(online_course, payment_model: PaymentModel) -> int:
    if payment_model == PaymentModel.WEEKLY:
        # Prefer explicit weekly price if set later; fall back to monthly/sessions.
        monthly = online_course.monthly_price or 0
        sessions = online_course.monthly_sessions or 4
        if sessions > 0 and monthly:
            return max(monthly // sessions, 0)
        return monthly
    if payment_model == PaymentModel.MONTHLY:
        return online_course.monthly_price or 0
    return online_course.term_price or 0


class OnlineEnrollmentService:
    """
    Enrolls a student in an online class.

    WEEKLY / MONTHLY: sessions are credited when an installment is marked paid
    (not at enrollment time). TERM credits all sessions immediately.
    """

    def __init__(self):
        self.repository = OnlineEnrollmentRepository()
        self.installment_service = InstallmentService()

    def create_enrollment(
        self,
        db: Session,
        user_id: int,
        online_course,
        payment_model: PaymentModel,
    ) -> OnlineEnrollment:

        if payment_model == PaymentModel.TERM:
            remaining = sessions_for_plan(online_course, payment_model)
            status = EnrollmentStatus.ACTIVE
        else:
            # Wait for first cycle payment before granting sessions.
            remaining = 0
            status = EnrollmentStatus.PAUSED

        enrollment = self.repository.create(
            db,
            OnlineEnrollment(
                user_id=user_id,
                online_course_id=online_course.id,
                payment_model=payment_model,
                remaining_sessions=remaining,
                status=status,
            ),
        )

        if payment_model in (PaymentModel.MONTHLY, PaymentModel.WEEKLY):
            self.installment_service.create_next_installment(db, enrollment)

        return enrollment

    def credit_sessions_after_payment(self, db: Session, enrollment: OnlineEnrollment) -> OnlineEnrollment:
        course = enrollment.online_course
        grant = sessions_for_plan(course, enrollment.payment_model)
        enrollment.remaining_sessions = (enrollment.remaining_sessions or 0) + grant
        enrollment.status = EnrollmentStatus.ACTIVE
        db.commit()
        db.refresh(enrollment)
        return enrollment

    def get_by_id(self, db: Session, enrollment_id: int):
        return self.repository.get_by_id(db, enrollment_id)

    def get_active_by_user(self, db: Session, user_id: int):
        return self.repository.get_active_by_user(db, user_id)
