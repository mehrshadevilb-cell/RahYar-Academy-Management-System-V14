"""Read/update student notification mute preferences."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.database.models.notification_preference import NotificationPreference

CATEGORIES = (
    "installment_reminders",
    "class_reminders",
    "broadcast_messages",
)

CATEGORY_LABELS_FA = {
    "installment_reminders": "یادآوری اقساط",
    "class_reminders": "یادآوری کلاس",
    "broadcast_messages": "پیام‌های همگانی",
}


class NotificationPreferenceService:
    def get_or_create(self, db: Session, user_id: int) -> NotificationPreference:
        pref = (
            db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user_id)
            .one_or_none()
        )
        if pref:
            return pref
        pref = NotificationPreference(
            user_id=user_id,
            installment_reminders=True,
            class_reminders=True,
            broadcast_messages=True,
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
        return pref

    def is_enabled(self, db: Session, user_id: int, category: str) -> bool:
        if category not in CATEGORIES:
            return True
        pref = (
            db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user_id)
            .one_or_none()
        )
        if pref is None:
            return True
        return bool(getattr(pref, category, True))

    def toggle(self, db: Session, user_id: int, category: str) -> NotificationPreference:
        if category not in CATEGORIES:
            raise ValueError(f"unknown category: {category}")
        pref = self.get_or_create(db, user_id)
        current = bool(getattr(pref, category))
        setattr(pref, category, not current)
        db.commit()
        db.refresh(pref)
        return pref

    def as_dict(self, pref: NotificationPreference) -> dict[str, bool]:
        return {key: bool(getattr(pref, key)) for key in CATEGORIES}
