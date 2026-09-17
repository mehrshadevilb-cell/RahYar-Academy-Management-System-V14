"""Canonical student identity and safe website-to-Telegram linking."""

from sqlalchemy import inspect, select, update
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
            if username is not None:
                account.username = username
            if phone:
                normalized = self.normalize_phone(phone)
                if normalized and not account.user.phone:
                    account.user.phone = normalized
            if full_name and not account.user.full_name:
                account.user.full_name = full_name[:100]
            db.commit()
            return account.user

        normalized_phone = self.normalize_phone(phone)
        # Keep the new Telegram row phone-less until an existing website lead
        # is merged; otherwise the unique phone constraint rejects the flush.
        live_user = User(full_name=(full_name or "هنرجو")[:100], phone=None)
        db.add(live_user)
        db.flush()
        from src.database.models.telegram_account import TelegramAccount

        db.add(TelegramAccount(user_id=live_user.id, telegram_id=telegram_id, username=username))
        db.flush()

        if normalized_phone:
            legacy = (
                db.query(User)
                .filter(User.phone == normalized_phone, User.id != live_user.id)
                .first()
            )
            if legacy and legacy.telegram_account is None:
                self.merge_users(db, source=legacy, destination=live_user, commit=False)

        if normalized_phone:
            live_user.phone = normalized_phone

        db.commit()
        return live_user

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

        # A verified destination profile wins; copy only missing identity data.
        # Release the legacy unique phone first so the destination can claim it
        # in the same transaction on PostgreSQL and SQLite.
        source_phone = source.phone
        if not destination.phone and source_phone:
            source.phone = None
            db.flush()
            destination.phone = source_phone
        if not destination.email and source.email:
            destination.email = source.email
        if not destination.full_name and source.full_name:
            destination.full_name = source.full_name

        # Referral has two user foreign keys and needs collision handling.
        for referral in db.query(Referral).filter(Referral.referrer_id == source.id).all():
            referral.referrer_id = destination.id
        existing_referred = db.query(Referral).filter(Referral.referred_id == destination.id).first()
        if existing_referred:
            db.query(Referral).filter(Referral.referred_id == source.id).delete(synchronize_session=False)
        else:
            db.query(Referral).filter(Referral.referred_id == source.id).update(
                {Referral.referred_id: destination.id}, synchronize_session=False
            )

        # Update every mapped table that has a user_id column. This makes future
        # student-owned tables part of the merge by default instead of silently
        # stranding records when a new feature is added.
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
