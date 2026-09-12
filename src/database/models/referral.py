from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class ReferralStatus(str, enum.Enum):
    PENDING = "pending"    # referred friend has registered but not paid yet
    REWARDED = "rewarded"  # referrer has already received their reward


class Referral(Base):
    """
    One row per referred (invited) student. `referred_id` is unique -
    a student can only ever be "referred" once (by whoever's link they
    first used), which also makes self-referral and reward farming via
    repeated re-registration impossible.

    The reward is granted exactly once, the moment the referred
    student's first payment is approved: this is enforced by only
    rewarding while `status == PENDING` and flipping it to `REWARDED`
    in the same step, not by tracking "which payment was the first".
    """

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    referrer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    referred_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True
    )

    status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus), default=ReferralStatus.PENDING
    )

    reward_discount_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("discount_codes.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
