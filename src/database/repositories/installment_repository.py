from sqlalchemy.orm import Session

from src.database.models.installment import Installment, InstallmentStatus


class InstallmentRepository:

    def create(self, db: Session, installment: Installment):
        db.add(installment)
        db.commit()
        db.refresh(installment)
        return installment

    def get_latest_for_enrollment(self, db: Session, enrollment_id: int):
        return (
            db.query(Installment)
            .filter(Installment.enrollment_id == enrollment_id)
            .order_by(Installment.installment_number.desc())
            .first()
        )

    def get_pending_for_enrollment(self, db: Session, enrollment_id: int):
        return (
            db.query(Installment)
            .filter(
                Installment.enrollment_id == enrollment_id,
                Installment.status == InstallmentStatus.PENDING,
            )
            .order_by(Installment.installment_number.desc())
            .first()
        )

    def get_by_id(self, db: Session, installment_id: int):
        return (
            db.query(Installment)
            .filter(Installment.id == installment_id)
            .first()
        )

    def get_pending(self, db: Session):
        return (
            db.query(Installment)
            .filter(Installment.status == InstallmentStatus.PENDING)
            .order_by(Installment.due_date)
            .all()
        )

    def get_overdue(self, db: Session):
        return (
            db.query(Installment)
            .filter(Installment.status == InstallmentStatus.OVERDUE)
            .order_by(Installment.due_date)
            .all()
        )
