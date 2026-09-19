from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.database.models.payment import Payment
from src.database.repositories.payment_repository import PaymentRepository

# Allowed status transitions for the manual card-to-card review flow.
REVIEWABLE_STATUSES = frozenset({"pending"})
TERMINAL_STATUSES = frozenset({"approved", "rejected", "cancelled", "refunded"})


class PaymentReviewError(ValueError):
    """Raised when a review action is illegal for the current status."""


class PaymentService:
    """
    Handles the manual card-to-card payment review flow:
    pending (receipt uploaded) -> approved / rejected by the owner.

    A license or course access must never be granted before a
    payment is explicitly approved by the owner.
    """

    def __init__(self):
        self.repository = PaymentRepository()

    def create_pending(
        self,
        db: Session,
        user_id: int,
        course_id: int,
        amount: int,
        receipt_file_id: str,
        discount_code_id: int | None = None,
        discount_amount: int = 0,
    ) -> Payment:
        payment = Payment(
            user_id=user_id,
            course_id=course_id,
            amount=amount,
            status="pending",
            receipt_file_id=receipt_file_id,
            discount_code_id=discount_code_id,
            discount_amount=discount_amount,
        )
        return self.repository.create(db, payment)

    def approve(
        self,
        db: Session,
        payment_id: int,
        admin_telegram_id: int,
    ) -> Payment | None:
        """Approve a pending payment. Idempotent against double-click:

        - missing id -> None
        - already approved -> same payment, no second side-effect here
        - rejected/cancelled -> PaymentReviewError
        """
        payment = self.repository.get_by_id_for_update(db, payment_id)
        if not payment:
            return None

        if payment.status == "approved":
            return payment

        if payment.status not in REVIEWABLE_STATUSES:
            raise PaymentReviewError(
                f"Cannot approve payment {payment_id} from status={payment.status!r}"
            )

        payment.status = "approved"
        payment.approved_by_id = admin_telegram_id
        payment.reviewed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(payment)
        return payment

    def reject(
        self,
        db: Session,
        payment_id: int,
        admin_telegram_id: int,
        reason: str | None = None,
    ) -> Payment | None:
        payment = self.repository.get_by_id_for_update(db, payment_id)
        if not payment:
            return None

        if payment.status == "rejected":
            return payment

        if payment.status not in REVIEWABLE_STATUSES:
            raise PaymentReviewError(
                f"Cannot reject payment {payment_id} from status={payment.status!r}"
            )

        payment.status = "rejected"
        payment.approved_by_id = admin_telegram_id
        payment.reviewed_at = datetime.now(timezone.utc)
        payment.admin_notes = reason

        db.commit()
        db.refresh(payment)
        return payment

    def get_by_id(self, db: Session, payment_id: int) -> Payment | None:
        return self.repository.get_by_id(db, payment_id)

    def get_pending(self, db: Session):
        return self.repository.get_pending(db)
