from datetime import date, timedelta

from sqlalchemy.orm import Session

from src.database.models.online_time_slot import OnlineTimeSlot, normalize_weekday
from src.database.models.reservation import Reservation, ReservationStatus
from src.database.models.online_enrollment import OnlineEnrollment
from src.core.utils.jalali import jalali_to_gregorian, gregorian_to_jalali, format_jalali_date


class OnlineScheduleService:
    """Admin-managed weekly slots and deterministic enrollment reservation plans."""

    def list_active_slots(self, db: Session, course_id: int):
        return (
            db.query(OnlineTimeSlot)
            .filter(OnlineTimeSlot.online_course_id == course_id, OnlineTimeSlot.is_active.is_(True))
            .order_by(OnlineTimeSlot.weekday, OnlineTimeSlot.start_time)
            .all()
        )

    def add_slot(self, db: Session, course_id: int, weekday: int, start_time: str, end_time: str):
        weekday = normalize_weekday(int(weekday))
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")
        slot = OnlineTimeSlot(
            online_course_id=course_id,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            is_active=True,
        )
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot

    def toggle_slot(self, db: Session, slot_id: int):
        slot = db.query(OnlineTimeSlot).filter(OnlineTimeSlot.id == slot_id).one_or_none()
        if not slot:
            return None
        slot.is_active = not slot.is_active
        db.commit()
        db.refresh(slot)
        return slot

    def slot_is_available(self, db: Session, enrollment_id: int, slot_id: int, start: date, count: int) -> bool:
        slot = db.query(OnlineTimeSlot).filter(OnlineTimeSlot.id == slot_id, OnlineTimeSlot.is_active.is_(True)).one_or_none()
        if not slot:
            return False
        dates = self.dates_for_slot(slot, start, count)
        occupied = {
            (item.requested_date, item.requested_time)
            for item in db.query(Reservation).join(OnlineEnrollment, Reservation.enrollment_id == OnlineEnrollment.id).filter(
                OnlineEnrollment.online_course_id == slot.online_course_id,
                Reservation.status.in_((ReservationStatus.WAITING_PAYMENT, ReservationStatus.PAYMENT_SUBMITTED, ReservationStatus.CONFIRMED)),
            ).all()
        }
        return all((self.iso_date(d), slot.start_time) not in occupied for d in dates)

    def dates_for_slot(self, slot: OnlineTimeSlot, start: date, count: int) -> list[date]:
        days = []
        current = start
        while len(days) < count:
            if current.weekday() == slot.weekday:
                days.append(current)
            current += timedelta(days=1)
        return days

    @staticmethod
    def iso_date(value: date) -> str:
        return value.isoformat()

    def create_reservation_plan(self, db: Session, enrollment, slot_id: int, start: date, count: int):
        slot = db.query(OnlineTimeSlot).filter(OnlineTimeSlot.id == slot_id, OnlineTimeSlot.is_active.is_(True)).one_or_none()
        if not slot or count <= 0:
            raise ValueError("invalid or inactive time slot")
        if not self.slot_is_available(db, enrollment.id, slot_id, start, count):
            raise ValueError("one or more selected sessions are already reserved")
        reservations = [
            Reservation(
                enrollment_id=enrollment.id,
                requested_date=self.iso_date(day),
                requested_time=slot.start_time,
                status=ReservationStatus.WAITING_PAYMENT,
                admin_notes=f"slot_id={slot.id}; plan_sessions={count}",
            )
            for day in self.dates_for_slot(slot, start, count)
        ]
        db.add_all(reservations)
        db.commit()
        for item in reservations:
            db.refresh(item)
        return reservations

    def create_jalali_reservation_plan(self, db: Session, enrollment, slot_id: int, jy: int, jm: int, jd: int, count: int):
        gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
        slot = db.query(OnlineTimeSlot).filter(OnlineTimeSlot.id == slot_id, OnlineTimeSlot.is_active.is_(True)).one_or_none()
        if not slot:
            raise ValueError("invalid or inactive time slot")
        if count <= 0:
            raise ValueError("reservation count must be positive")
        if not self.slot_is_available(db, enrollment.id, slot_id, date(gy, gm, gd), count):
            raise ValueError("one or more selected sessions are already reserved")
        reservations = []
        for day in self.dates_for_slot(slot, date(gy, gm, gd), count):
            jy2, jm2, jd2 = gregorian_to_jalali(day.year, day.month, day.day)
            reservations.append(Reservation(
                enrollment_id=enrollment.id,
                requested_date=format_jalali_date(jy2, jm2, jd2),
                requested_time=slot.start_time,
                status=ReservationStatus.WAITING_PAYMENT,
                admin_notes=f"slot_id={slot.id}; plan_sessions={count}",
            ))
        db.add_all(reservations)
        db.commit()
        return reservations
