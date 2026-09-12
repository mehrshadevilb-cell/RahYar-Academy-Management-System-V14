import asyncio

from src.bot.bot import bot, dp, setup_handlers
from src.database.seed_payment_card import seed_default_card
from src.database.seed_products import seed_default_products
from src.database.seed_online_courses import seed_default_online_courses
from src.services.reminder_scheduler import InstallmentReminderScheduler
from src.core.logging.logger import get_logger


logger = get_logger("main")


async def main():

    logger.info("Starting RahYar Bot...")

    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        logger.info("Database migrated successfully")

    except Exception as e:
        logger.exception(f"Database migration error: {e}")
        raise


    seed_default_card()
    seed_default_products()
    seed_default_online_courses()


    setup_handlers()

    scheduler = InstallmentReminderScheduler(bot)
    scheduler.start()


    try:
        await dp.start_polling(bot)

    finally:
        await bot.session.close()



if __name__ == "__main__":
    asyncio.run(main())
