from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
import traceback

from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.bot.telegram_errors import is_benign_telegram_error, should_notify_owner

from src.bot.handlers import start, course, profile, my_courses, payment, admin
from src.bot.handlers import online_class, admin_online_enrollment, admin_online, admin_installments
from src.bot.handlers import admin_discount, admin_logs, admin_broadcast, admin_reports
from src.bot.handlers import admin_ai, admin_ai_self_check, referral, support, admin_support
from src.bot.handlers import assignment, admin_assignments, progress
from src.bot.handlers import music_generator, group_music_panel
from src.bot.handlers import chat_assistant, notifications, admin_dashboard
from src.bot.middlewares.database import DatabaseMiddleware
from src.bot.middlewares.security import SecurityMiddleware
from src.services.ai_agent_knowledge_runtime import AIAgentKnowledgeRuntime

settings = get_settings()
logger = get_logger("bot.errors")


def build_fsm_storage():
    url = (settings.REDIS_URL or "").strip()
    if not url:
        logger.info("FSM storage: MemoryStorage (REDIS_URL not set)")
        return MemoryStorage()
    try:
        from aiogram.fsm.storage.redis import RedisStorage
        storage = RedisStorage.from_url(url)
        logger.info("FSM storage: RedisStorage")
        return storage
    except Exception:
        logger.exception("FSM Redis init failed; falling back to MemoryStorage")
        return MemoryStorage()


session = AiohttpSession(proxy=settings.PROXY_URL) if settings.PROXY_URL else None
bot = Bot(token=settings.BOT_TOKEN, session=session)
dp = Dispatcher(storage=build_fsm_storage())
dp.message.middleware(DatabaseMiddleware())
dp.callback_query.middleware(DatabaseMiddleware())
dp.message.middleware(SecurityMiddleware())
dp.callback_query.middleware(SecurityMiddleware())

ai_agent_knowledge = AIAgentKnowledgeRuntime(bot=bot)


async def send_error_report(event: ErrorEvent, exc: Exception):
    if not settings.OWNER_ID:
        return

    update = event.update
    user_id = None
    username = None
    chat_id = None

    if update.message:
        chat_id = update.message.chat.id
        if update.message.from_user:
            user_id = update.message.from_user.id
            username = update.message.from_user.username

    report = (
        "🚨 RahYar Bot Error\n\n"
        f"Update: {getattr(update, 'update_id', '-') }\n"
        f"User: {user_id}\n"
        f"Username: @{username}\n"
        f"Chat: {chat_id}\n\n"
        f"Exception: {type(exc).__name__}\n"
        f"Message: {str(exc)[:700]}\n\n"
        f"Traceback:\n{traceback.format_exc()[:2500]}"
    )

    try:
        await bot.send_message(chat_id=settings.OWNER_ID, text=report)
    except Exception:
        logger.exception("Failed sending admin error report")


@dp.error()
async def global_error_handler(event: ErrorEvent):
    exc = event.exception
    callback_query = event.update.callback_query

    if callback_query:
        try:
            await callback_query.answer()
        except Exception:
            logger.exception("Failed callback answer")

    if isinstance(exc, TelegramConflictError):
        logger.warning("Telegram conflict: %s", exc)
        return True

    if isinstance(exc, TelegramUnauthorizedError):
        logger.error("Telegram token invalid")
        return True

    if is_benign_telegram_error(exc):
        logger.info("Benign Telegram error: %s", exc)
        return True

    logger.exception("Unhandled error: %s", exc)
    await send_error_report(event, exc)

    chat_id = None
    if event.update.message:
        chat_id = event.update.message.chat.id
    elif callback_query and callback_query.message:
        chat_id = callback_query.message.chat.id

    if chat_id:
        try:
            await bot.send_message(chat_id=chat_id, text="⚠️ متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید یا از «🆘 پشتیبانی» پیام بگذارید.")
        except Exception:
            logger.exception("Failed user error message")

    if settings.OWNER_ID and should_notify_owner(exc):
        try:
            await bot.send_message(chat_id=settings.OWNER_ID, text=f"🚨 خطای فنی: {type(exc).__name__}\n{str(exc)[:500]}")
        except Exception:
            logger.exception("Failed owner notification")

    return True


def setup_handlers():
    for module in (
        start, course, profile, notifications, my_courses, payment, admin, admin_dashboard,
        online_class, admin_online_enrollment, admin_online, admin_installments, admin_discount,
        admin_logs, admin_broadcast, admin_reports, admin_ai, admin_ai_self_check,
        referral, support, admin_support, assignment, admin_assignments,
        progress, group_music_panel, music_generator, ai_agent_knowledge,
        chat_assistant,
    ):
        dp.include_router(module.router)
