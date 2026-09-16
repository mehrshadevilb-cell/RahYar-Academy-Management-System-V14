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
    """Owner- or self-initiated enrollment in a live online class."""

    def __init__(self):
        self.repository = OnlineEnrollmentRepository()
        self.installment_service = InstallmentService()

    def create_enrollment(
        self,
        db: Session,
        user_id: int,
        online_course,
        payment_model: PaymentModel,
        *,
        remaining_sessions: int | None = None,
        custom_amount: int | None = None,
        admin_notes: str | None = None,
    ) -> OnlineEnrollment:

        if remaining_sessions is None:
            remaining_sessions = (
                online_course.monthly_sessions
                if payment_model == PaymentModel.MONTHLY
                else online_course.term_sessions
            )

        enrollment = self.repository.create(
            db,
            OnlineEnrollment(
                user_id=user_id,
                online_course_id=online_course.id,
                payment_model=payment_model,
                remaining_sessions=max(0, int(remaining_sessions)),
                admin_notes=admin_notes,
            ),
        )

        if payment_model == PaymentModel.MONTHLY:
            amount = custom_amount
            if amount is None:
                amount = online_course.monthly_price or 0
            self.installment_service.create_next_installment(
                db, enrollment, amount=amount
            )

        return enrollment

    def get_by_id(self, db: Session, enrollment_id: int):
        return self.repository.get_by_id(db, enrollment_id)

    def get_active_by_user(self, db: Session, user_id: int):
        return self.repository.get_active_by_user(db, user_id)

    def get_by_course(self, db: Session, online_course_id: int):
        return self.repository.get_by_course(db, online_course_id)

    def get_active_for_user_course(self, db: Session, user_id: int, online_course_id: int):
        return self.repository.get_active_for_user_course(db, user_id, online_course_id)

    def adjust_remaining_sessions(
        self, db: Session, enrollment: OnlineEnrollment, delta: int
    ) -> OnlineEnrollment:
        enrollment.remaining_sessions = max(0, enrollment.remaining_sessions + int(delta))
        return self.repository.save(db, enrollment)

    def set_remaining_sessions(
        self, db: Session, enrollment: OnlineEnrollment, value: int
    ) -> OnlineEnrollment:
        enrollment.remaining_sessions = max(0, int(value))
        return self.repository.save(db, enrollment)

    def set_status(
        self, db: Session, enrollment: OnlineEnrollment, status: EnrollmentStatus
    ) -> OnlineEnrollment:
        enrollment.status = status
        return self.repository.save(db, enrollment)

    def set_admin_notes(
        self, db: Session, enrollment: OnlineEnrollment, notes: str | None
    ) -> OnlineEnrollment:
        enrollment.admin_notes = (notes or "")[:500] or None
        return self.repository.save(db, enrollment)

    def set_custom_fee(
        self, db: Session, enrollment: OnlineEnrollment, amount: int
    ):
        """Update the latest pending installment amount, or create one."""
        amount = max(0, int(amount))
        return self.installment_service.set_or_create_pending_amount(
            db, enrollment, amount
        )
