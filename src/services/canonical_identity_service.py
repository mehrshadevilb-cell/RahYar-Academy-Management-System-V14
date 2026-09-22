"""Canonical student identity and safe website-to-Telegram linking."""

from sqlalchemy import update
from sqlalchemy.orm import Session

from src.database.base import Base
from src.database.models.referral import Referral
from src.database.models.user import User


class CanonicalIdentityError(ValueError):
    pass


class CanonicalIdentityService:
    """Keeps one User row as the canonical owner of all student records."""

    def normalize_phone(self, phone: str | None) -> str | None:
        if not phone:
            return None
        digits = "".join(ch for ch in str(phone) if ch.isdigit())
        if digits.startswith("0098"):
            digits = "0" + digits[4:]
        elif digits.startswith("98"):
            digits = "0" + digits[2:]
        elif len(digits) == 10 and digits.startswith("9"):
            digits = "0" + digits
        if len(digits) != 11 or not digits.startswith("09"):
            return None
        return digits

    def link_telegram_account(
        self,
        db: Session,
        *,
        telegram_id: str,
        full_name: str,
        phone: str | None = None,
        username: str | None = None,
    ) -> User:
        """Resolve Telegram identity and merge an unlinked website lead if needed."""
        from src.database.models.telegram_account import TelegramAccount

        telegram_id = str(telegram_id).strip()
        if not telegram_id:
            raise CanonicalIdentityError("telegram_id_required")

        account = db.query(TelegramAccount).filter(TelegramAccount.telegram_id == telegram_id).first()
        if account:
            user = account.user
            if username is not None:
                account.username = username
            # Telegram is the authoritative identity source for the display
            # name while the account is being synchronized.
            if full_name:
                user.full_name = full_name[:100]
            normalized = self.normalize_phone(phone)
            if normalized and not user.phone:
                user.phone = normalized
            db.commit()
            db.refresh(user)
            return user

        normalized_phone = self.normalize_phone(phone)

        # First try to attach to an existing website lead by phone. This is
        # important when a student registered on the website before opening
        # the Telegram Mini App.
        legacy = None
        if normalized_phone:
            legacy = db.query(User).filter(User.phone == normalized_phone).first()
            if legacy and legacy.telegram_account is not None:
                raise CanonicalIdentityError("telegram_phone_already_linked")

        if legacy is not None:
            user = legacy
            user.full_name = (full_name or user.full_name or "هنرجو")[:100]
            db.add(TelegramAccount(user_id=user.id, telegram_id=telegram_id, username=username))
            db.commit()
            db.refresh(user)
            return user

        user = User(full_name=(full_name or "هنرجو")[:100], phone=normalized_phone)
        db.add(user)
        db.flush()
        db.add(TelegramAccount(user_id=user.id, telegram_id=telegram_id, username=username))
        db.commit()
        db.refresh(user)
        return user

    def merge_users(
        self,
        db: Session,
        *,
        source: User,
        destination: User,
        commit: bool = True,
    ) -> User:
        """Move every user-owned row to destination, preserving the canonical row."""
        if source.id == destination.id:
            return destination
        if source.telegram_account is not None:
            raise CanonicalIdentityError("source_telegram_account_must_be_unlinked")
        if destination.telegram_account is None:
            raise CanonicalIdentityError("destination_must_be_telegram_linked")

        source_phone = source.phone
        if not destination.phone and source_phone:
            source.phone = None
            db.flush()
            destination.phone = source_phone
        if not destination.email and source.email:
            destination.email = source.email
        if not destination.full_name and source.full_name:
            destination.full_name = source.full_name

        for referral in db.query(Referral).filter(Referral.referrer_id == source.id).all():
            referral.referrer_id = destination.id
        existing_referred = db.query(Referral).filter(Referral.referred_id == destination.id).first()
        if existing_referred:
            db.query(Referral).filter(Referral.referred_id == source.id).delete(synchronize_session=False)
        else:
            db.query(Referral).filter(Referral.referred_id == source.id).update(
                {Referral.referred_id: destination.id}, synchronize_session=False
            )

        for table in Base.metadata.tables.values():
            if table.name in {"users", "telegram_accounts", "referrals"} or "user_id" not in table.c:
                continue
            db.execute(
                update(table)
                .where(table.c.user_id == source.id)
                .values(user_id=destination.id)
            )

        db.delete(source)
        db.flush()
        if commit:
            db.commit()
        return destination
