from datetime import datetime

from sqlalchemy.orm import Session

from src.database.models.payment import Payment
from src.database.repositories.payment_repository import PaymentRepository


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
        admin_id: int,
    ) -> Payment | None:

        payment = self.repository.get_by_id(db, payment_id)

        if not payment:
            return None

        payment.status = "approved"
        payment.approved_by_id = admin_id
        payment.reviewed_at = datetime.utcnow()

        db.commit()
        db.refresh(payment)

        return payment

    def reject(
        self,
        db: Session,
        payment_id: int,
        admin_id: int,
        reason: str | None = None,
    ) -> Payment | None:

        payment = self.repository.get_by_id(db, payment_id)

        if not payment:
            return None

        payment.status = "rejected"
        payment.approved_by_id = admin_id
        payment.reviewed_at = datetime.utcnow()
        payment.admin_notes = reason

        db.commit()
        db.refresh(payment)

        return payment

    def get_by_id(self, db: Session, payment_id: int) -> Payment | None:
        return self.repository.get_by_id(db, payment_id)


    def get_pending(self, db: Session):
        return self.repository.get_pending(db)
