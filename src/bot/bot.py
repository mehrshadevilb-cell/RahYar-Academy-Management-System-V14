from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import ErrorEvent

from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger

from src.bot.handlers import start
from src.bot.handlers import course
from src.bot.handlers import profile
from src.bot.handlers import my_courses
from src.bot.handlers import payment
from src.bot.handlers import admin
from src.bot.handlers import online_class
from src.bot.handlers import admin_online
from src.bot.handlers import admin_installments
from src.bot.handlers import admin_discount
from src.bot.handlers import admin_logs
from src.bot.handlers import admin_broadcast
from src.bot.handlers import admin_reports
from src.bot.handlers import referral

from src.bot.middlewares.database import DatabaseMiddleware



settings = get_settings()



session = (
    AiohttpSession(proxy=settings.PROXY_URL)
    if settings.PROXY_URL
    else None
)



bot = Bot(
    token=settings.BOT_TOKEN,
    session=session,
)



dp = Dispatcher()



dp.message.middleware(
    DatabaseMiddleware()
)

dp.callback_query.middleware(
    DatabaseMiddleware()
)


logger = get_logger("bot.errors")


@dp.error()
async def global_error_handler(event: ErrorEvent):
    """
    Catches any exception that escapes a handler so a bug never crashes
    the whole bot (per PROJECT_CONTEXT.md Section 20): logs the full
    traceback for debugging, tells whoever was chatting that something
    went wrong (no stack trace, no internals), and separately alerts the
    owner with technical detail so it doesn't only live in server logs.
    """

    logger.exception(
        "Unhandled error on update %s: %s",
        event.update.update_id,
        event.exception,
        exc_info=event.exception,
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
                text="⚠️ متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
            )
        except Exception:
            logger.exception("Failed to notify user %s about an error", chat_id)

    if settings.OWNER_ID:
        try:
            await bot.send_message(
                chat_id=settings.OWNER_ID,
                text=(
                    "🚨 خطای فنی در ربات\n\n"
                    f"نوع: {type(event.exception).__name__}\n"
                    f"پیام: {event.exception}"
                ),
            )
        except Exception:
            logger.exception("Failed to notify owner about an error")

    return True


def setup_handlers():


    dp.include_router(
        start.router
    )


    dp.include_router(
        course.router
    )


    dp.include_router(
        profile.router
    )


    dp.include_router(
        my_courses.router
    )


    dp.include_router(
        payment.router
    )


    dp.include_router(
        admin.router
    )


    dp.include_router(
        online_class.router
    )


    dp.include_router(
        admin_online.router
    )


    dp.include_router(
        admin_installments.router
    )


    dp.include_router(
        admin_discount.router
    )


    dp.include_router(
        admin_logs.router
    )


    dp.include_router(
        admin_broadcast.router
    )


    dp.include_router(
        admin_reports.router
    )


    dp.include_router(
        referral.router
    )