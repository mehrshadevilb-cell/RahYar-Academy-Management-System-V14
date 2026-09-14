from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from aiogram.types import ErrorEvent

from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.bot.telegram_errors import is_benign_telegram_error, should_notify_owner

from src.bot.handlers import start, course, profile, my_courses, payment, admin
from src.bot.handlers import online_class, admin_online, admin_installments
from src.bot.handlers import admin_discount, admin_logs, admin_broadcast, admin_reports
from src.bot.handlers import admin_ai, referral, support, admin_support
from src.bot.handlers import assignment, admin_assignments, progress
from src.bot.handlers import chat_assistant
from src.bot.middlewares.database import DatabaseMiddleware

settings = get_settings()

session = AiohttpSession(proxy=settings.PROXY_URL) if settings.PROXY_URL else None
bot = Bot(token=settings.BOT_TOKEN, session=session)
dp = Dispatcher()

dp.message.middleware(DatabaseMiddleware())
dp.callback_query.middleware(DatabaseMiddleware())

logger = get_logger("bot.errors")


@dp.error()
async def global_error_handler(event: ErrorEvent):
    exc = event.exception

    # Infrastructure noise during rolling deploys — do not spam users/owner.
    if isinstance(exc, TelegramConflictError):
        logger.warning("TelegramConflictError (another getUpdates active): %s", exc)
        return True
    if isinstance(exc, TelegramUnauthorizedError):
        logger.error("TelegramUnauthorizedError — BOT_TOKEN invalid or revoked")
        return True

    if is_benign_telegram_error(exc):
        logger.info(
            "Benign Telegram error on update %s: %s: %s",
            event.update.update_id,
            type(exc).__name__,
            exc,
        )
        return True

    logger.exception(
        "Unhandled error on update %s: %s",
        event.update.update_id,
        exc,
        exc_info=exc,
    )

    chat_id = None
    if event.update.message:
        chat_id = event.update.message.chat.id
    elif event.update.callback_query and event.update.callback_query.message:
        chat_id = event.update.callback_query.message.chat.id

    if chat_id:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "⚠️ متأسفانه خطایی رخ داد. "
                    "لطفاً دوباره تلاش کنید یا از «🆘 پشتیبانی» پیام بگذارید."
                ),
            )
        except Exception:
            logger.exception("Failed to notify user %s about an error", chat_id)

    if settings.OWNER_ID and should_notify_owner(exc):
        try:
            await bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    f"🚨 خطای فنی در ربات\n\n"
                    f"نوع: {type(exc).__name__}\n"
                    f"پیام: {str(exc)[:500]}"
                ),
            )
        except Exception:
            logger.exception("Failed to notify owner about an error")
    return True


def setup_handlers():
    for module in (
        start, course, profile, my_courses, payment, admin, online_class,
        admin_online, admin_installments, admin_discount, admin_logs,
        admin_broadcast, admin_reports, admin_ai, referral, support, admin_support,
        assignment, admin_assignments, progress,
        chat_assistant,
    ):
        dp.include_router(module.router)
