"""
Website orders share the same users + payments tables as the Telegram bot.

Access is never granted from the website alone: a payment stays pending
until the owner approves it in Telegram (same rule as bot receipts).
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from src.database.models.course import Course
from src.database.models.payment import Payment
from src.database.models.payment_card import PaymentCard
from src.database.models.user import User, UserRole
from src.database.repositories.course_repository import CourseRepository
from src.database.repositories.payment_repository import PaymentRepository
from src.services.online_course_service import OnlineCourseService

PHONE_RE = re.compile(r"^09\d{9}$")


class WebOrderError(ValueError):
    pass


class WebOrderService:

    def __init__(self) -> None:
        self.courses = CourseRepository()
        self.payments = PaymentRepository()
        self.online_courses = OnlineCourseService()

    def list_products(self, db: Session) -> list[Course]:
        return self.courses.get_active_courses(db)

    def get_product(self, db: Session, product_id: int) -> Course | None:
        product = self.courses.get_by_id(db, product_id)
        if not product or not product.is_active:
            return None
        return product

    def list_online_classes(self, db: Session):
        return self.online_courses.get_active_courses(db)

    def get_online_class(self, db: Session, course_id: int):
        course = self.online_courses.get_course_by_id(db, course_id)
        if not course or not course.is_active:
            return None
        return course

    def get_active_card(self, db: Session) -> PaymentCard | None:
        return (
            db.query(PaymentCard)
            .filter(PaymentCard.is_active.is_(True))
            .order_by(PaymentCard.id.asc())
            .first()
        )

    def normalize_phone(self, phone: str) -> str:
        raw = (phone or "").strip().replace(" ", "").replace("-", "")
        if raw.startswith("+98"):
            raw = "0" + raw[3:]
        if raw.startswith("98") and len(raw) == 12:
            raw = "0" + raw[2:]
        if not PHONE_RE.match(raw):
            raise WebOrderError("invalid_phone")
        return raw

    def ensure_user(self, db: Session, *, full_name: str, phone: str) -> User:
        full_name = (full_name or "").strip()
        if len(full_name) < 2:
            raise WebOrderError("invalid_name")
        phone = self.normalize_phone(phone)

        existing = db.query(User).filter(User.phone == phone).first()
        if existing:
            if full_name and existing.full_name != full_name:
                existing.full_name = full_name
                db.commit()
                db.refresh(existing)
            return existing

        user = User(full_name=full_name, phone=phone, role=UserRole.STUDENT)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def create_product_order(
        self,
        db: Session,
        *,
        product_id: int,
        full_name: str,
        phone: str,
        note: str | None = None,
    ) -> tuple[User, Payment, Course]:
        product = self.get_product(db, product_id)
        if not product:
            raise WebOrderError("product_unavailable")

        user = self.ensure_user(db, full_name=full_name, phone=phone)
        order_ref = uuid.uuid4().hex[:12]
        receipt_marker = f"web:{order_ref}"
        if note:
            receipt_marker = f"web:{order_ref}|{(note or '')[:80]}"

        payment = Payment(
            user_id=user.id,
            course_id=product.id,
            amount=product.price,
            status="pending",
            receipt_file_id=receipt_marker,
            admin_notes="سفارش از وب‌سایت — در انتظار رسید/تأیید",
        )
        payment = self.payments.create(db, payment)
        return user, payment, product

    def get_product_order_status(
        self,
        db: Session,
        *,
        payment_id: int,
        phone: str,
    ) -> tuple[User, Payment, Course] | None:
        """Return a product order only when its payment id and phone match.

        The phone check prevents the public tracking endpoint from becoming a
        payment-enumeration API while keeping the flow usable without a full
        student account.
        """
        normalized_phone = self.normalize_phone(phone)
        row = (
            db.query(User, Payment, Course)
            .join(Payment, Payment.user_id == User.id)
            .join(Course, Course.id == Payment.course_id)
            .filter(
                Payment.id == payment_id,
                User.phone == normalized_phone,
            )
            .first()
        )
        return row
