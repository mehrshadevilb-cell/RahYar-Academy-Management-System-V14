import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from sqlalchemy.orm import Session

from src.database.repositories.telegram_repository import TelegramRepository


logger = logging.getLogger("broadcast")

# Telegram allows roughly ~30 messages/second globally and is strict about
# hammering the same bot too fast; a small per-message delay keeps a large
# broadcast well under that without needing a queue/worker infrastructure.
DEFAULT_DELAY_SECONDS = 0.05


@dataclass
class BroadcastResult:
    total: int = 0
    sent: int = 0
    blocked: int = 0
    failed: int = 0


class BroadcastService:
    """
    Relays one admin-authored message (any content type: text, photo,
    voice, ...) to every student with a linked Telegram account, via
    `Bot.copy_message` so the admin never has to re-type the content per
    delivery type.

    This intentionally has no persistent "campaign" model - each run is a
    fire-and-forget fan-out over the current audience. If that changes
    (e.g. scheduled/segmented broadcasts), a Broadcast/BroadcastLog model
    should be added rather than growing this service ad-hoc.
    """

    def __init__(self, delay_seconds: float = DEFAULT_DELAY_SECONDS):
        self.telegram_repository = TelegramRepository()
        self.delay_seconds = delay_seconds

    def get_audience(self, db: Session):
        """Every linked Telegram account, used as the broadcast target list."""

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
        """
        Copies the given message to every account in the audience.

        `exclude_telegram_ids` lets the caller skip the admin's own chat
        (they already saw the message as the preview).

        `on_progress(sent_so_far, total)` is called periodically so the
        handler can update a "in progress" message without this service
        knowing anything about Telegram UI concerns beyond sending.
        """

        exclude_telegram_ids = exclude_telegram_ids or set()
        audience = [
            account
            for account in self.get_audience(db)
            if account.telegram_id not in exclude_telegram_ids
        ]

        result = BroadcastResult(total=len(audience))

        for index, account in enumerate(audience, start=1):
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
            # Flood control: wait the mandated time and retry once.
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
                logger.exception(
                    "Broadcast retry failed for telegram_id=%s", account.telegram_id
                )

        except TelegramForbiddenError:
            # User blocked the bot or deleted their account - expected and
            # not worth logging as an error.
            result.blocked += 1

        except TelegramAPIError:
            result.failed += 1
            logger.exception(
                "Broadcast send failed for telegram_id=%s", account.telegram_id
            )
