from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import exists
from sqlalchemy.orm import Session

from src.core.config.settings import get_settings
from src.database.models.enrollment import Enrollment
from src.database.models.payment import Payment
from src.database.models.telegram_account import TelegramAccount
from src.database.models.user import User


class MusicQuota:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._memory: dict[str, tuple[int, datetime]] = {}
        self._redis = None
        if self.settings.REDIS_URL:
            try:
                from redis import Redis
                self._redis = Redis.from_url(self.settings.REDIS_URL, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    def is_rah_yar_student(self, db: Session, telegram_id: int | str) -> bool:
        paid = exists().where(Payment.user_id == User.id, Payment.status == "approved")
        enrolled = exists().where(Enrollment.user_id == User.id)
        row = (
            db.query(User)
            .join(TelegramAccount, TelegramAccount.user_id == User.id)
            .filter(TelegramAccount.telegram_id == str(telegram_id), User.is_active.is_(True))
            .first()
        )
        if not row:
            return False
        return bool(db.query(exists().where(Payment.user_id == row.id, Payment.status == "approved")).scalar() or db.query(exists().where(Enrollment.user_id == row.id)).scalar())

    @staticmethod
    def _seconds_until_reset() -> int:
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(60, int((tomorrow - now).total_seconds()))

    def limit_for(self, is_student: bool) -> int:
        return self.settings.MUSIC_GENERATION_RAHYAR_DAILY_LIMIT if is_student else self.settings.MUSIC_GENERATION_PUBLIC_DAILY_LIMIT

    def reserve(self, telegram_id: int | str, is_student: bool) -> tuple[bool, int, int]:
        limit = self.limit_for(is_student)
        key = f"rahyar:music:generation:{datetime.now(timezone.utc):%Y-%m-%d}:{telegram_id}"
        if self._redis:
            try:
                count = int(self._redis.incr(key))
                if count == 1:
                    self._redis.expire(key, self._seconds_until_reset())
                if count > limit:
                    self._redis.decr(key)
                    return False, limit, limit
                return True, limit, max(0, limit - count)
            except Exception:
                pass
        now = datetime.now(timezone.utc)
        count, expires = self._memory.get(key, (0, now + timedelta(seconds=self._seconds_until_reset())))
        if expires <= now:
            count = 0
            expires = now + timedelta(seconds=self._seconds_until_reset())
        count += 1
        if count > limit:
            return False, limit, 0
        self._memory[key] = (count, expires)
        return True, limit, max(0, limit - count)

    def release(self, telegram_id: int | str) -> None:
        key = f"rahyar:music:generation:{datetime.now(timezone.utc):%Y-%m-%d}:{telegram_id}"
        if self._redis:
            try:
                self._redis.decr(key)
                return
            except Exception:
                pass
        count, expires = self._memory.get(key, (0, datetime.now(timezone.utc)))
        self._memory[key] = (max(0, count - 1), expires)
