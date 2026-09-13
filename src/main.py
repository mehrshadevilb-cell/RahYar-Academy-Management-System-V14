import asyncio
import os
import threading

from fastapi import FastAPI
import uvicorn

from src.bot.bot import bot, dp, setup_handlers
from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.database.seed_payment_card import seed_default_card
from src.database.seed_products import seed_default_products
from src.database.seed_online_courses import seed_default_online_courses
from src.services.reminder_scheduler import InstallmentReminderScheduler


settings = get_settings()
logger = get_logger("rahyar.main")


app = FastAPI(
    title="RahYar Academy Management System"
)


@app.get("/")
async def health_check():
    return {
        "status": "running",
        "service": "RahYar Bot"
    }


@app.get("/health")
async def health():
    return {
        "ok": True
    }



async def start_bot():

    logger.info("Starting RahYar Bot...")

    # Schema changes are applied by Alembic (see docs/MIGRATIONS.md)
    # before this process starts. Seeds are intentionally idempotent,
    # so it's safe to always run them here.
    seed_default_card()
    seed_default_products()
    seed_default_online_courses()

    setup_handlers()

    installment_scheduler = InstallmentReminderScheduler(bot)
    installment_scheduler.start()

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    finally:
        await bot.session.close()



def run_web():

    # Render (and most PaaS platforms) assign the port dynamically via
    # the PORT env var and route traffic/health-checks to it - a
    # hardcoded port here would make health checks fail intermittently.
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )



async def main():

    logger.info("Booting application...")


    web_thread = threading.Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()


    await start_bot()



if __name__ == "__main__":

    asyncio.run(main())
