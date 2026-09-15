from datetime import datetime

from sqlalchemy.orm import Session

from src.database.models.discount_code import DiscountCode, DiscountType
from src.database.repositories.discount_code_repository import DiscountCodeRepository


class DiscountCodeService:
    """
    Owns every business rule around discount codes: creation, validity
    checks at redemption time, and the price calculation itself.

    Usage accounting is a two-step reservation, not a single "redeem":
    `reserve_usage` runs the moment a student's code is accepted and a
    pending payment is created with it, and `release_usage_by_id` runs
    if that payment is later rejected.
    """

    def __init__(self):
        self.repository = DiscountCodeRepository()

    @staticmethod
    def normalize_code(raw_code: str) -> str:
        return (raw_code or "").strip().upper()

    # ---------------- Admin CRUD ----------------

    def create_code(
        self,
        db: Session,
        code: str,
        discount_type: DiscountType,
        value: int,
        max_uses: int | None,
        expires_at: datetime | None,
    ) -> DiscountCode | None:
        """Returns None if a code with the same (normalized) text already
        exists - the caller/handler is responsible for showing a friendly
        Persian error in that case."""
        normalized = self.normalize_code(code)

        if self.repository.get_by_code(db, normalized):
            return None

        return self.repository.create(
            db,
            DiscountCode(
                code=normalized,
                discount_type=discount_type,
                value=value,
                max_uses=max_uses,
                expires_at=expires_at,
            ),
        )

    def get_all(self, db: Session) -> list[DiscountCode]:
        return self.repository.get_all(db)

    def get_by_id(self, db: Session, code_id: int) -> DiscountCode | None:
        return self.repository.get_by_id(db, code_id)

    def code_exists(self, db: Session, code: str) -> bool:
        return self.repository.get_by_code(db, self.normalize_code(code)) is not None

    def toggle_active(self, db: Session, code_id: int) -> DiscountCode | None:
        discount_code = self.repository.get_by_id(db, code_id)
        if not discount_code:
            return None

        discount_code.is_active = not discount_code.is_active
        db.commit()
        db.refresh(discount_code)
        return discount_code

    # ---------------- Redemption ----------------

    def validate(
        self,
        db: Session,
        raw_code: str,
        price: int,
    ) -> tuple[DiscountCode | None, int, int, str | None]:
        """
        Checks a student-entered code against every business rule.

        The redemption path uses SELECT ... FOR UPDATE so the max_uses
        check and the following reservation cannot race with another buyer.
        """
        normalized = self.normalize_code(raw_code)
        discount_code = self.repository.get_by_code_for_update(db, normalized)

        if not discount_code:
            return None, price, 0, "❌ کد تخفیف نامعتبر است."

        if not discount_code.is_active:
            return None, price, 0, "❌ این کد تخفیف غیرفعال شده است."

        if discount_code.expires_at and discount_code.expires_at < datetime.utcnow():
            return None, price, 0, "❌ مهلت استفاده از این کد تخفیف به پایان رسیده است."

        if (
            discount_code.max_uses is not None
            and discount_code.used_count >= discount_code.max_uses
        ):
            return None, price, 0, "❌ ظرفیت استفاده از این کد تخفیف تمام شده است."

        final_price, discount_amount = self.calculate_discounted_price(
            price, discount_code
        )
        return discount_code, final_price, discount_amount, None

    @staticmethod
    def calculate_discounted_price(
        price: int, discount_code: DiscountCode
    ) -> tuple[int, int]:
        """Returns (final_price, discount_amount). The discount can never
        exceed the price itself (no negative payment amounts)."""
        if discount_code.discount_type == DiscountType.PERCENTAGE:
            raw_discount = price * discount_code.value // 100
        else:
            raw_discount = discount_code.value

        discount_amount = max(0, min(raw_discount, price))
        final_price = price - discount_amount
        return final_price, discount_amount

    def reserve_usage(self, db: Session, discount_code: DiscountCode) -> None:
        discount_code.used_count += 1
        db.commit()

    def release_usage_by_id(self, db: Session, discount_code_id: int) -> None:
        discount_code = self.repository.get_by_id(db, discount_code_id)
        if not discount_code:
            return

        discount_code.used_count = max(0, discount_code.used_count - 1)
        db.commit()
