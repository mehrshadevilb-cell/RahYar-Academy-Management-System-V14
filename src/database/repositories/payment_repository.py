from sqlalchemy.orm import Session

from src.database.models.payment import Payment


class PaymentRepository:
    def create(self, db: Session, payment: Payment):
        db.add(payment)
        db.commit()
        db.refresh(payment)
        return payment

    def get_by_id(self, db: Session, payment_id: int):
        return db.query(Payment).filter(Payment.id == payment_id).first()

    def get_by_id_for_update(self, db: Session, payment_id: int):
        """Lock the payment row until the surrounding transaction commits.

        On SQLite (tests) FOR UPDATE is a no-op / may be ignored; on
        PostgreSQL production this serializes concurrent approve/reject.
        """
        return (
            db.query(Payment)
            .filter(Payment.id == payment_id)
            .with_for_update()
            .first()
        )

    def get_pending(self, db: Session):
        return (
            db.query(Payment)
            .filter(Payment.status == "pending")
            .order_by(Payment.id.desc())
            .all()
        )

    def get_for_user(self, db: Session, user_id: int, *, limit: int = 5):
        return (
            db.query(Payment)
            .filter(Payment.user_id == user_id)
            .order_by(Payment.id.desc())
            .limit(limit)
            .all()
        )
