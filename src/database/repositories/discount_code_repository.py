from sqlalchemy.orm import Session

from src.database.models.discount_code import DiscountCode


class DiscountCodeRepository:

    def get_by_id(self, db: Session, code_id: int) -> DiscountCode | None:
        return (
            db.query(DiscountCode)
            .filter(DiscountCode.id == code_id)
            .first()
        )

    def get_by_code(self, db: Session, code: str) -> DiscountCode | None:
        return (
            db.query(DiscountCode)
            .filter(DiscountCode.code == code)
            .first()
        )

    def get_by_code_for_update(
        self,
        db: Session,
        code: str,
    ) -> DiscountCode | None:
        """Load a code with a row lock for the validate -> reserve flow.

        The purchase handler validates the code and immediately reserves a
        usage slot in the same DB session. Locking here prevents two
        concurrent buyers from both passing the max_uses check.
        """
        return (
            db.query(DiscountCode)
            .filter(DiscountCode.code == code)
            .with_for_update()
            .first()
        )

    def get_all(self, db: Session) -> list[DiscountCode]:
        return (
            db.query(DiscountCode)
            .order_by(DiscountCode.id.desc())
            .all()
        )

    def create(self, db: Session, discount_code: DiscountCode) -> DiscountCode:
        db.add(discount_code)
        db.commit()
        db.refresh(discount_code)
        return discount_code
