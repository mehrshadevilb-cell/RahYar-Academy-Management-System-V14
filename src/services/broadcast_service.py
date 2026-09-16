import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from sqlalchemy.orm import Session

from src.database.repositories.telegram_repository import TelegramRepository
from src.services.notification_preference_service import NotificationPreferenceService

logger = logging.getLogger("broadcast")
DEFAULT_DELAY_SECONDS = 0.05


@dataclass
class BroadcastResult:
    total: int = 0
    sent: int = 0
    blocked: int = 0
    failed: int = 0
    skipped_muted: int = 0


class BroadcastService:
    def __init__(self, delay_seconds: float = DEFAULT_DELAY_SECONDS):
        self.telegram_repository = TelegramRepository()
        self.pref_service = NotificationPreferenceService()
        self.delay_seconds = delay_seconds

    def get_audience(self, db: Session):
        return self.telegram_repository.get_all(db)

    async def send(
        self,
        bot: Bot,
        db: Session,
        from_chat_id: int,
        message_id: int,
        exclude_telegram_ids: set[str] | None = None,
        on_progress=None,
    ) -> BroadcastResult:
        exclude_telegram_ids = exclude_telegram_ids or set()
        audience = [
            account
            for account in self.get_audience(db)
            if account.telegram_id not in exclude_telegram_ids
        ]
        result = BroadcastResult(total=len(audience))

        for index, account in enumerate(audience, start=1):
            user_id = getattr(account, "user_id", None)
            if user_id is not None and not self.pref_service.is_enabled(
                db, int(user_id), "broadcast_messages"
            ):
                result.skipped_muted += 1
            else:
                await self._send_one(bot, from_chat_id, message_id, account, result)

            if on_progress and (index % 20 == 0 or index == result.total):
                try:
                    await on_progress(index, result.total)
                except Exception:
                    logger.exception("Broadcast progress callback failed")

            await asyncio.sleep(self.delay_seconds)

        return result

    async def _send_one(self, bot, from_chat_id, message_id, account, result: BroadcastResult):
        try:
            await bot.copy_message(
                chat_id=int(account.telegram_id),
                from_chat_id=from_chat_id,
                message_id=message_id,
            )
            result.sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.copy_message(
                    chat_id=int(account.telegram_id),
                    from_chat_id=from_chat_id,
                    message_id=message_id,
                )
                result.sent += 1
            except TelegramForbiddenError:
                result.blocked += 1
            except TelegramAPIError:
                result.failed += 1
                logger.exception("Broadcast retry failed for telegram_id=%s", account.telegram_id)
        except TelegramForbiddenError:
            result.blocked += 1
        except TelegramAPIError:
            result.failed += 1
            logger.exception("Broadcast send failed for telegram_id=%s", account.telegram_id)
