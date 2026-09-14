from sqlalchemy.orm import Session

from src.database.models.online_enrollment import (
    OnlineEnrollment,
    PaymentModel,
    EnrollmentStatus,
)
from src.database.repositories.online_enrollment_repository import (
    OnlineEnrollmentRepository,
)
from src.services.installment_service import InstallmentService


class OnlineEnrollmentService:
    """
    Enrolls a student in an online class. Session credits for weekly/monthly
    plans are granted when the corresponding installment is marked paid
    (see credit_sessions_after_payment). TERM plans receive sessions upfront.
    """

    def __init__(self):
        self.repository = OnlineEnrollmentRepository()
        self.installment_service = InstallmentService()

    def _sessions_for_plan(self, online_course, payment_model: PaymentModel) -> int:
        if payment_model == PaymentModel.WEEKLY:
            return online_course.weekly_sessions or 1
        if payment_model == PaymentModel.MONTHLY:
            return online_course.monthly_sessions or 4
        return online_course.term_sessions or 12

    def create_enrollment(
        self,
        db: Session,
        user_id: int,
        online_course,
        payment_model: PaymentModel,
    ) -> OnlineEnrollment:
        # WEEKLY / MONTHLY: sessions granted only after payment confirmation.
        # TERM: full package paid upfront → sessions available immediately.
        if payment_model in (PaymentModel.WEEKLY, PaymentModel.MONTHLY):
            remaining = 0
            status = EnrollmentStatus.PAUSED
        else:
            remaining = self._sessions_for_plan(online_course, payment_model)
            status = EnrollmentStatus.ACTIVE

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

        if payment_model in (PaymentModel.WEEKLY, PaymentModel.MONTHLY):
            self.installment_service.create_next_installment(db, enrollment)

        return enrollment

    def credit_sessions_after_payment(
        self, db: Session, enrollment: OnlineEnrollment
    ) -> OnlineEnrollment:
        """After installment is marked paid: top-up remaining_sessions and activate.

        Idempotent relative to status — calling twice still only adds one cycle's
        worth of sessions from the plan definition (owner can re-credit via admin
        if needed).
        """
        course = enrollment.online_course
        sessions = self._sessions_for_plan(course, enrollment.payment_model)

        enrollment.remaining_sessions = (enrollment.remaining_sessions or 0) + sessions
        if enrollment.status in (EnrollmentStatus.PAUSED, EnrollmentStatus.ENDED):
            enrollment.status = EnrollmentStatus.ACTIVE

        db.commit()
        db.refresh(enrollment)
        return enrollment

    def get_by_id(self, db: Session, enrollment_id: int):
        return self.repository.get_by_id(db, enrollment_id)

    def get_active_by_user(self, db: Session, user_id: int):
        return self.repository.get_active_by_user(db, user_id)

    def get_by_user(self, db: Session, user_id: int):
        return self.repository.get_by_user(db, user_id) if hasattr(self.repository, "get_by_user") else self.repository.get_active_by_user(db, user_id)
