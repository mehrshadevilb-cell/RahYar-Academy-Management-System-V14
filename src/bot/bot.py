from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.bot.telegram_errors import is_benign_telegram_error, should_notify_owner

from src.bot.handlers import start, course, profile, my_courses, payment, admin
from src.bot.handlers import online_class, admin_online, admin_installments
from src.bot.handlers import admin_discount, admin_logs, admin_broadcast, admin_reports
from src.bot.handlers import admin_ai, referral, support, admin_support
from src.bot.handlers import assignment, admin_assignments, progress
from src.bot.handlers import music_generator
from src.bot.handlers import chat_assistant
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

# The Telegram router is only a transport adapter. Knowledge intelligence belongs to the AI Agent runtime.
ai_agent_knowledge = AIAgentKnowledgeRuntime(bot=bot)


@dp.error()
async def global_error_handler(event: ErrorEvent):
    exc = event.exception
    callback_query = event.update.callback_query
    if callback_query:
        try:
            await callback_query.answer()
        except Exception:
            logger.exception("Failed to answer callback_query %s after an error", callback_query.id)
    if isinstance(exc, TelegramConflictError):
        logger.warning("TelegramConflictError (another getUpdates active): %s", exc)
        return True
    if isinstance(exc, TelegramUnauthorizedError):
        logger.error("TelegramUnauthorizedError — BOT_TOKEN invalid or revoked")
        return True
    if is_benign_telegram_error(exc):
        logger.info("Benign Telegram error on update %s: %s: %s", event.update.update_id, type(exc).__name__, exc)
        return True
    logger.exception("Unhandled error on update %s: %s", event.update.update_id, exc, exc_info=exc)
    chat_id = None
    if event.update.message:
        chat_id = event.update.message.chat.id
    elif callback_query and callback_query.message:
        chat_id = callback_query.message.chat.id
    if chat_id:
        try:
            await bot.send_message(chat_id=chat_id, text="⚠️ متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید یا از «🆘 پشتیبانی» پیام بگذارید.")
        except Exception:
            logger.exception("Failed to notify user %s about an error", chat_id)
    if settings.OWNER_ID and should_notify_owner(exc):
        try:
            await bot.send_message(chat_id=settings.OWNER_ID, text=f"🚨 خطای فنی در ربات\n\nنوع: {type(exc).__name__}\nپیام: {str(exc)[:500]}")
        except Exception:
            logger.exception("Failed to notify owner: %s", settings.OWNER_ID)
    return True


def setup_handlers():
    for module in (
        start, course, profile, my_courses, payment, admin, online_class,
        admin_online, admin_installments, admin_discount, admin_logs,
        admin_broadcast, admin_reports, admin_ai, referral, support, admin_support,
        assignment, admin_assignments, progress, music_generator,
        # AI Agent transport gateway; it owns the knowledge/support intelligence.
        ai_agent_knowledge,
        # chat_assistant MUST stay last: it is a free-text catch-all.
        chat_assistant,
    ):
        dp.include_router(module.router)
