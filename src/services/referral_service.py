import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.database.models.referral import Referral, ReferralStatus
from src.database.models.discount_code import DiscountType
from src.database.repositories.referral_repository import ReferralRepository
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.discount_code_service import DiscountCodeService

# Reward given to the referrer once their invitee's first payment is
# approved - a single-use, time-limited discount code (kept as named
# constants rather than magic numbers so the academy owner's intent is
# visible in one place if these ever need tuning).
REFERRAL_REWARD_PERCENTAGE = 15
REFERRAL_REWARD_VALIDITY_DAYS = 30
REFERRAL_CODE_PREFIX = "REF"


class ReferralService:
    """
    A student can only ever be referred once (`Referral.referred_id` is
    unique), and a referrer is only ever rewarded once per invitee -
    exactly when that invitee's first payment is approved, tracked by
    flipping `status` from PENDING to REWARDED rather than by counting
    payments. Self-referral is structurally impossible: the referrer
    must already have a Telegram account, which a brand-new user (the
    only case this is ever called for) cannot yet have under their own id.
    """

    def __init__(self):
        self.repository = ReferralRepository()
        self.telegram_repository = TelegramRepository()
        self.discount_code_service = DiscountCodeService()

    def create_referral_if_eligible(
        self,
        db: Session,
        referrer_telegram_id: str,
        referred_user_id: int,
    ) -> Referral | None:
        """Called only for a brand-new user's very first /start. Returns
        None (silently - an invalid/expired referral code shouldn't
        block registration) if the code doesn't resolve to a real
        referrer or anything else looks off."""

        if self.repository.get_by_referred_id(db, referred_user_id):
            return None

        referrer_account = self.telegram_repository.get_by_telegram_id(
            db, referrer_telegram_id
        )

        if not referrer_account:
            return None

        referrer_id = referrer_account.user_id

        if referrer_id == referred_user_id:
            return None

        return self.repository.create(
            db,
            Referral(referrer_id=referrer_id, referred_id=referred_user_id),
        )

    def reward_referrer_if_pending(
        self,
        db: Session,
        referred_user_id: int,
    ) -> Referral | None:
        """Called after a payment is approved. Returns the updated
        Referral (with its fresh reward code attached) if a reward was
        actually granted just now, or None if there was nothing to do
        (no referral, or it was already rewarded)."""

        referral = self.repository.get_by_referred_id(db, referred_user_id)

        if not referral or referral.status != ReferralStatus.PENDING:
            return None

        code = self._issue_unique_reward_code(db)

        referral.reward_discount_code_id = code.id
        referral.status = ReferralStatus.REWARDED
        referral.rewarded_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(referral)

        return referral

    def _issue_unique_reward_code(self, db: Session):
        # Collisions are astronomically unlikely (a random 6-hex-char
        # suffix), but create_code() returning None on a duplicate is
        # handled defensively with a small retry loop rather than
        # assumed away.
        for _ in range(5):
            candidate = f"{REFERRAL_CODE_PREFIX}{secrets.token_hex(3).upper()}"

            code = self.discount_code_service.create_code(
                db=db,
                code=candidate,
                discount_type=DiscountType.PERCENTAGE,
                value=REFERRAL_REWARD_PERCENTAGE,
                max_uses=1,
                expires_at=datetime.now(timezone.utc) + timedelta(days=REFERRAL_REWARD_VALIDITY_DAYS),
            )

            if code:
                return code

        raise RuntimeError("Could not generate a unique referral discount code")

    def get_by_referrer(self, db: Session, referrer_id: int) -> list[Referral]:
        return self.repository.get_by_referrer_id(db, referrer_id)
