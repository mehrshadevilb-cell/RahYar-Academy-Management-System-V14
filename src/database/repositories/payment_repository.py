from sqlalchemy.orm import Session

from src.database.models.payment import Payment



class PaymentRepository:


    def create(
        self,
        db: Session,
        payment: Payment,
    ):

        db.add(payment)

        db.commit()

        db.refresh(payment)

        return payment



    def get_by_id(
        self,
        db: Session,
        payment_id: int,
    ):

        return (
            db.query(Payment)
            .filter(
                Payment.id == payment_id
            )
            .first()
        )


    def get_pending(
        self,
        db: Session,
    ):

        return (
            db.query(Payment)
            .filter(Payment.status == "pending")
            .order_by(Payment.id.desc())
            .all()
        )
