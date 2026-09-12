from sqlalchemy.orm import Session

from src.database.models.payment_card import PaymentCard


class PaymentCardRepository:

    def get_active(self, db: Session) -> PaymentCard | None:

        return (
            db.query(PaymentCard)
            .filter(PaymentCard.is_active.is_(True))
            .order_by(PaymentCard.id.desc())
            .first()
        )

    def create(self, db: Session, card: PaymentCard) -> PaymentCard:

        db.add(card)
        db.commit()
        db.refresh(card)

        return card

    def get_all(self, db: Session):

        return (
            db.query(PaymentCard)
            .order_by(PaymentCard.id.desc())
            .all()
        )

    def deactivate_all(self, db: Session) -> None:

        db.query(PaymentCard).update({PaymentCard.is_active: False})
        db.commit()
