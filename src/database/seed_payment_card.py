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
from src.core.logging.logger import get_logger

logger = get_logger("rahyar.seed.payment_card")


def seed_default_card() -> None:
    settings = get_settings()

    if not settings.DEFAULT_CARD_NUMBER or not settings.DEFAULT_CARD_HOLDER:
        logger.info(
            "DEFAULT_CARD_NUMBER / DEFAULT_CARD_HOLDER not set - skipping card seed."
        )
        return

    db = SessionLocal()
    try:
        existing = (
            db.query(PaymentCard)
            .filter(PaymentCard.card_number == settings.DEFAULT_CARD_NUMBER)
            .first()
        )

        if existing:
            logger.info("Default card already exists - skipping.")
            return

        card = PaymentCard(
            card_number=settings.DEFAULT_CARD_NUMBER,
            card_holder=settings.DEFAULT_CARD_HOLDER,
            is_active=True,
        )
        db.add(card)
        db.commit()
        logger.info("Default payment card added.")
    except Exception:
        db.rollback()
        logger.exception("seed_default_card failed; continuing startup")
    finally:
        db.close()


if __name__ == "__main__":
    seed_default_card()
