"""Website account registration with safe legacy-record claiming."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.core.security.password import hash_password
from src.database.models.student_profile import StudentProfile
from src.database.models.user import User, UserRole
from src.services.web_order_service import WebOrderError, WebOrderService


class WebRegistrationError(ValueError):
    """Raised for a website registration conflict or invalid input."""


@dataclass(frozen=True)
class WebRegistrationResult:
    user: User
    claimed_existing_record: bool


class WebRegistrationService:
    """Create a web account or claim a pre-website student record by phone.

    SpotPlayer imports, bot-only users, and unclaimed web orders may already
    have a canonical ``User`` row.  They have no ``password_hash`` because
    they have never registered on the website.  The first website registration
    claims that row and preserves its purchases instead of falsely reporting a
    duplicate number.  A password-bearing row is an actual prior website
    account and remains protected from duplicate registration.
    """

    def __init__(self, order_service: WebOrderService | None = None) -> None:
        self.order_service = order_service or WebOrderService()

    def register(
        self,
        db: Session,
        *,
        full_name: str,
        phone: str,
        password: str,
    ) -> WebRegistrationResult:
        name = (full_name or "").strip()
        if len(name) < 2:
            raise WebRegistrationError("invalid_name")
        if len(password or "") < 6:
            raise WebRegistrationError("invalid_password")
        try:
            normalized_phone = self.order_service.normalize_phone(phone)
        except WebOrderError as exc:
            raise WebRegistrationError("invalid_phone") from exc

        existing = db.query(User).filter(User.phone == normalized_phone).first()
        if existing is not None:
            if existing.password_hash:
                raise WebRegistrationError("phone_already_registered")

            existing.full_name = name[:100]
            existing.password_hash = hash_password(password)
            existing.is_active = True
            if existing.role != UserRole.ADMIN:
                existing.role = UserRole.STUDENT
            if existing.student_profile is None:
                db.add(StudentProfile(user_id=existing.id))
            db.commit()
            db.refresh(existing)
            return WebRegistrationResult(user=existing, claimed_existing_record=True)

        user = User(
            full_name=name[:100],
            phone=normalized_phone,
            password_hash=hash_password(password),
            role=UserRole.STUDENT,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(StudentProfile(user_id=user.id))
        db.commit()
        db.refresh(user)
        return WebRegistrationResult(user=user, claimed_existing_record=False)
