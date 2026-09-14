"""Telegram API error classification and safe send helpers.

Handlers and services should prefer these helpers over bare bot.send_*
when failures are expected (blocked users, rate limits, stale callbacks).
"""

from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)

from src.core.logging.logger import get_logger

logger = get_logger("bot.telegram_errors")


def is_benign_telegram_error(exc: BaseException) -> bool:
    """Errors that should not alarm the owner or the end user."""
    if isinstance(exc, TelegramForbiddenError):
        return True
    if isinstance(exc, TelegramBadRequest):
        msg = str(exc).lower()
        benign_markers = (
            "chat not found",
            "user is deactivated",
            "bot was blocked",
            "message is not modified",
            "message to edit not found",
            "message to delete not found",
            "query is too old",
            "query id is invalid",
        )
        return any(m in msg for m in benign_markers)
    return False


def should_notify_owner(exc: BaseException) -> bool:
    if is_benign_telegram_error(exc):
        return False
    if isinstance(exc, TelegramRetryAfter):
        return False
    if isinstance(exc, TelegramNetworkError):
        return False
    return True


async def safe_send_message(
    bot: Bot,
    chat_id: int | str,
    text: str,
    *,
    max_retries: int = 2,
    **kwargs: Any,
) -> bool:
    """Send a message; return False if the user cannot receive it."""
    attempt = 0
    while True:
        try:
            await bot.send_message(chat_id=chat_id, text=text, **kwargs)
            return True
        except TelegramRetryAfter as exc:
            attempt += 1
            if attempt > max_retries:
                logger.warning("RetryAfter exhausted for chat %s", chat_id)
                return False
            await asyncio.sleep(float(exc.retry_after) + 0.5)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if is_benign_telegram_error(exc):
                logger.info("Skip send to %s: %s", chat_id, type(exc).__name__)
                return False
            logger.warning("BadRequest sending to %s: %s", chat_id, exc)
            return False
        except TelegramUnauthorizedError:
            logger.error("Bot token unauthorized while sending to %s", chat_id)
            raise
        except TelegramNetworkError as exc:
            attempt += 1
            if attempt > max_retries:
                logger.warning("Network error sending to %s: %s", chat_id, exc)
                return False
            await asyncio.sleep(1.5 * attempt)
