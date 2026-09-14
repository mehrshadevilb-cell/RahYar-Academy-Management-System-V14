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


# Sessions granted per paid installment cycle (monthly payment unit).
SESSIONS_PER_CYCLE = 4


class OnlineEnrollmentService:
    """
    Enrolls a student in an online class.

    Business rule:
    - Classes meet once per week.
    - Payment is monthly (4 sessions) or term (12 sessions ≈ 3 monthly cycles).
    - Session credits are granted when the corresponding installment is marked paid.
    """

    def __init__(self):
        self.repository = OnlineEnrollmentRepository()
        self.installment_service = InstallmentService()

    def _sessions_per_payment(self, online_course, payment_model: PaymentModel) -> int:
        """How many sessions one confirmed payment unlocks."""
        if payment_model == PaymentModel.MONTHLY:
            return online_course.monthly_sessions or SESSIONS_PER_CYCLE
        # TERM: each installment cycle still unlocks one month of sessions (4).
        # The term length is enforced by max installments / total completed.
        return online_course.monthly_sessions or SESSIONS_PER_CYCLE

    def _term_total_sessions(self, online_course) -> int:
        return online_course.term_sessions or 12

    def _max_installments_for_term(self, online_course) -> int:
        total = self._term_total_sessions(online_course)
        per = online_course.monthly_sessions or SESSIONS_PER_CYCLE
        return max(1, (total + per - 1) // per)  # e.g. 12/4 = 3

    def create_enrollment(
        self,
        db: Session,
        user_id: int,
        online_course,
        payment_model: PaymentModel,
    ) -> OnlineEnrollment:
        # Both MONTHLY and TERM start paused until first payment is confirmed.
        # Sessions are credited in credit_sessions_after_payment.
        enrollment = self.repository.create(
            db,
            OnlineEnrollment(
                user_id=user_id,
                online_course_id=online_course.id,
                payment_model=payment_model,
                remaining_sessions=0,
                status=EnrollmentStatus.PAUSED,
            ),
        )

        self.installment_service.create_next_installment(db, enrollment)
        return enrollment

    def credit_sessions_after_payment(
        self, db: Session, enrollment: OnlineEnrollment
    ) -> OnlineEnrollment:
        """After installment is marked paid: top-up remaining_sessions and activate."""
        course = enrollment.online_course
        sessions = self._sessions_per_payment(course, enrollment.payment_model)

        enrollment.remaining_sessions = (enrollment.remaining_sessions or 0) + sessions
        if enrollment.status in (EnrollmentStatus.PAUSED, EnrollmentStatus.ENDED):
            enrollment.status = EnrollmentStatus.ACTIVE

        db.commit()
        db.refresh(enrollment)
        return enrollment

    def should_create_next_cycle(self, enrollment: OnlineEnrollment) -> bool:
        """Whether to open another installment after the current cycle is exhausted."""
        if enrollment.payment_model == PaymentModel.MONTHLY:
            return True
        # TERM: stop after 3 cycles (or whatever term_sessions implies).
        max_inst = self._max_installments_for_term(enrollment.online_course)
        return enrollment.current_installment_number < max_inst

    def get_by_id(self, db: Session, enrollment_id: int):
        return self.repository.get_by_id(db, enrollment_id)

    def get_active_by_user(self, db: Session, user_id: int):
        return self.repository.get_active_by_user(db, user_id)

    def get_by_user(self, db: Session, user_id: int):
        if hasattr(self.repository, "get_by_user"):
            return self.repository.get_by_user(db, user_id)
        return self.repository.get_active_by_user(db, user_id)
