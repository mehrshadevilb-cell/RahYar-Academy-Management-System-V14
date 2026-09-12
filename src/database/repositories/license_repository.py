from sqlalchemy.orm import Session

from src.database.models.license import License


class LicenseRepository:

    def create(self, db: Session, license_: License) -> License:

        db.add(license_)
        db.commit()
        db.refresh(license_)

        return license_

    def get_by_id(self, db: Session, license_id: int) -> License | None:

        return (
            db.query(License)
            .filter(License.id == license_id)
            .first()
        )

    def get_by_user_and_product(
        self,
        db: Session,
        user_id: int,
        product_id: int,
    ) -> License | None:

        return (
            db.query(License)
            .filter(
                License.user_id == user_id,
                License.product_id == product_id,
            )
            .order_by(License.id.desc())
            .first()
        )
