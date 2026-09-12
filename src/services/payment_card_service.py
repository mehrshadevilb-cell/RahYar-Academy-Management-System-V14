from sqlalchemy.orm import Session

from src.database.repositories.payment_card_repository import PaymentCardRepository


class PaymentCardService:
    """
    Provides the currently active card-to-card payment destination.
    The owner manages cards from the admin panel; nothing is hardcoded here.
    """

    def __init__(self):
        self.repository = PaymentCardRepository()

    def get_active_card(self, db: Session):
        return self.repository.get_active(db)

    def get_all_cards(self, db: Session):
        return self.repository.get_all(db)

    def add_card(self, db: Session, card_number: str, card_holder: str):
        """New card becomes the only active one; old cards are kept for
        history but deactivated, per the rule of never deleting records."""

        from src.database.models.payment_card import PaymentCard

        self.repository.deactivate_all(db)

        return self.repository.create(
            db,
            PaymentCard(
                card_number=card_number,
                card_holder=card_holder,
                is_active=True,
            ),
        )
