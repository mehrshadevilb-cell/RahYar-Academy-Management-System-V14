"""
Seeds the initial card-to-card payment card from environment variables.

The card number is sensitive financial information and must never be
hardcoded in source code - it is read from .env (DEFAULT_CARD_NUMBER /
DEFAULT_CARD_HOLDER) once, then lives only in the database from that
point on. Managing/replacing cards afterwards is an admin-panel task.
"""

from src.database.session import SessionLocal
from src.database.models.payment_card import PaymentCard
from src.core.config.settings import get_settings


def seed_default_card():

    settings = get_settings()

    if not settings.DEFAULT_CARD_NUMBER or not settings.DEFAULT_CARD_HOLDER:
        print(
            "DEFAULT_CARD_NUMBER / DEFAULT_CARD_HOLDER not set in .env - "
            "skipping card seed."
        )
        return

    db = SessionLocal()

    existing = (
        db.query(PaymentCard)
        .filter(PaymentCard.card_number == settings.DEFAULT_CARD_NUMBER)
        .first()
    )

    if existing:
        print("Default card already exists - skipping.")
        db.close()
        return

    card = PaymentCard(
        card_number=settings.DEFAULT_CARD_NUMBER,
        card_holder=settings.DEFAULT_CARD_HOLDER,
        is_active=True,
    )

    db.add(card)
    db.commit()
    db.close()

    print("Default payment card added.")


if __name__ == "__main__":
    seed_default_card()
