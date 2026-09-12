from datetime import date

from sqlalchemy.orm import Session

from src.database.models.online_enrollment import OnlineEnrollment, PaymentModel
from src.database.repositories.online_enrollment_repository import (
    OnlineEnrollmentRepository,
)
from src.services.installment_service import InstallmentService


class OnlineEnrollmentService:
    """
    Enrolls a student in an online class. This is an owner-initiated
    action (the owner negotiates schedule/teacher/payment model with the
    student directly, per the academy's existing process), not a
    self-serve purchase like the digital products.
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

        remaining = (
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
                remaining_sessions=remaining,
            ),
        )

        if payment_model == PaymentModel.MONTHLY:
            self.installment_service.create_next_installment(db, enrollment)

        return enrollment

    def get_by_id(self, db: Session, enrollment_id: int):
        return self.repository.get_by_id(db, enrollment_id)

    def get_active_by_user(self, db: Session, user_id: int):
        return self.repository.get_active_by_user(db, user_id)
