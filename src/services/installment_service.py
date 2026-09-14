from datetime import date

from sqlalchemy.orm import Session

from src.database.models.installment import Installment, InstallmentStatus
from src.database.models.online_enrollment import PaymentModel
from src.database.repositories.installment_repository import InstallmentRepository


class InstallmentService:
    """
    Creates installment (payment cycle) records for weekly/monthly online
    students. Due-date offset for auto-created cycles is "today".

    Reminder cadence (7/3/1 days before + due date) is fixed at 7/3/1/0
    per the confirmed business requirement.
    """

    REMINDER_OFFSETS = (
        (7, "reminder_7d_sent"),
        (3, "reminder_3d_sent"),
        (1, "reminder_1d_sent"),
        (0, "reminder_due_sent"),
    )

    def __init__(self):
        self.repository = InstallmentRepository()

    def _amount_for_enrollment(self, enrollment) -> int:
        course = enrollment.online_course
        if enrollment.payment_model == PaymentModel.WEEKLY:
            return course.weekly_price or 0
        if enrollment.payment_model == PaymentModel.MONTHLY:
            return course.monthly_price or 0
        return course.term_price or 0

    def create_next_installment(self, db: Session, enrollment) -> Installment:
        next_number = enrollment.current_installment_number + 1
        amount = self._amount_for_enrollment(enrollment)

        installment = self.repository.create(
            db,
            Installment(
                enrollment_id=enrollment.id,
                installment_number=next_number,
                amount=amount,
                due_date=date.today(),
            ),
        )

        enrollment.current_installment_number = next_number
        db.commit()
        return installment

    def mark_paid(self, db: Session, installment: Installment) -> Installment:
        """Idempotent: re-confirming an already-paid installment is a no-op."""

        if installment.status == InstallmentStatus.PAID:
            return installment

        installment.status = InstallmentStatus.PAID
        installment.paid_date = date.today()
        db.commit()
        db.refresh(installment)
        return installment

    def get_by_id(self, db: Session, installment_id: int) -> Installment | None:
        return self.repository.get_by_id(db, installment_id)

    def get_pending(self, db: Session) -> list[Installment]:
        return self.repository.get_pending(db)

    def get_overdue(self, db: Session) -> list[Installment]:
        return self.repository.get_overdue(db)

    def get_reminder_batch(self, db: Session) -> list[tuple[Installment, int]]:
        today = date.today()
        batch: list[tuple[Installment, int]] = []

        for installment in self.repository.get_pending(db):
            days_left = (installment.due_date - today).days

            for offset, flag_name in self.REMINDER_OFFSETS:
                if days_left == offset and not getattr(installment, flag_name):
                    batch.append((installment, offset))
                    break

        return batch

    def mark_reminder_sent(self, db: Session, installment: Installment, offset_days: int) -> None:
        flag_name = dict(self.REMINDER_OFFSETS)[offset_days]
        setattr(installment, flag_name, True)
        db.commit()

    def sync_overdue(self, db: Session) -> list[Installment]:
        today = date.today()
        newly_overdue: list[Installment] = []

        for installment in self.repository.get_pending(db):
            if installment.due_date < today:
                installment.status = InstallmentStatus.OVERDUE
                newly_overdue.append(installment)

        if newly_overdue:
            db.commit()

        return newly_overdue
