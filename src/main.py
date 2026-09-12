import asyncio

from src.bot.bot import bot, dp, setup_handlers

from src.database.connection import engine
from src.database.models import *

from src.database.seed_payment_card import seed_default_card
from src.database.seed_products import seed_default_products
from src.database.seed_online_courses import seed_default_online_courses

from src.services.reminder_scheduler import InstallmentReminderScheduler
from src.core.logging.logger import get_logger

logger = get_logger("main")


async def main():
    logger.info("Starting RahYar Bot...")

    # Create database tables on startup
    try:
        from src.database.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

    # Seed default data
    seed_default_card()
    seed_default_products()
    seed_default_online_courses()

    setup_handlers()

    installment_scheduler = InstallmentReminderScheduler(bot)
    installment_scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
