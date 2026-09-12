from datetime import date

from sqlalchemy.orm import Session

from src.database.models.installment import Installment, InstallmentStatus
from src.database.repositories.installment_repository import InstallmentRepository


class InstallmentService:
    """
    Creates installment (payment cycle) records for monthly-plan online
    students. Due-date offset for auto-created cycles is assumed to be
    "today" (i.e. due as soon as the previous cycle's sessions finish) -
    this is a reasonable default the owner can adjust once a settings
    panel for it exists; it is not a guess about SpotPlayer/Telegram
    provider behavior, just a business default.

    Reminder cadence (7/3/1 days before + due date) is fixed at 7/3/1/0
    per the confirmed business requirement. Each offset has its own
    "sent" flag on the model, so a reminder is never sent twice even if
    the scheduler runs more than once on the same day.
    """

    # (days_before_due, flag_attribute_name)
    REMINDER_OFFSETS = (
        (7, "reminder_7d_sent"),
        (3, "reminder_3d_sent"),
        (1, "reminder_1d_sent"),
        (0, "reminder_due_sent"),
    )

    def __init__(self):
        self.repository = InstallmentRepository()

    def create_next_installment(self, db: Session, enrollment) -> Installment:

        next_number = enrollment.current_installment_number + 1

        amount = enrollment.online_course.monthly_price or 0

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
        """Idempotent: re-confirming an already-paid installment is a no-op
        so a Telegram double-click or provider retry can't create a second
        payment event for the same cycle."""

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
        """Return (installment, days_before_due) pairs that need a
        reminder sent right now. Only PENDING installments are eligible -
        once something is PAID or OVERDUE it drops out of this list
        naturally, so there's no separate "cancel reminder" bookkeeping
        needed. At most one reminder per installment per call, using the
        closest matching offset that hasn't been sent yet."""

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
        """Transition PENDING installments whose due date has passed into
        OVERDUE. Returns only the installments that were transitioned in
        this call (i.e. newly overdue), so callers can send a one-time
        overdue notice without re-notifying every day - the status change
        itself is the idempotency guard, since a query for PENDING will
        never return this installment again."""

        today = date.today()
        newly_overdue: list[Installment] = []

        for installment in self.repository.get_pending(db):
            if installment.due_date < today:
                installment.status = InstallmentStatus.OVERDUE
                newly_overdue.append(installment)

        if newly_overdue:
            db.commit()

        return newly_overdue
