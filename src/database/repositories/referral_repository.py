from sqlalchemy.orm import Session

from src.database.models.referral import Referral


class ReferralRepository:

    def get_by_referred_id(self, db: Session, referred_id: int) -> Referral | None:
        return (
            db.query(Referral)
            .filter(Referral.referred_id == referred_id)
            .first()
        )

    def get_by_id(self, db: Session, referral_id: int) -> Referral | None:
        return (
            db.query(Referral)
            .filter(Referral.id == referral_id)
            .first()
        )

    def get_by_referrer_id(self, db: Session, referrer_id: int) -> list[Referral]:
        return (
            db.query(Referral)
            .filter(Referral.referrer_id == referrer_id)
            .order_by(Referral.id.desc())
            .all()
        )

    def create(self, db: Session, referral: Referral) -> Referral:
        db.add(referral)
        db.commit()
        db.refresh(referral)
        return referral
