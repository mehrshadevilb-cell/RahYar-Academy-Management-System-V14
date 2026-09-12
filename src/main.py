import asyncio
import threading
import uvicorn

from fastapi import FastAPI

from src.bot.bot import bot, dp, setup_handlers
from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger


settings = get_settings()
logger = get_logger("rahyar.main")


app = FastAPI(
    title="RahYar Academy Management System"
)


@app.get("/")
async def health_check():
    return {
        "status": "running",
        "service": "RahYar Telegram Bot"
    }


@app.get("/health")
async def health():
    return {
        "ok": True
    }



async def start_bot():

    logger.info("Starting RahYar Bot...")

    setup_handlers()

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    finally:
        await bot.session.close()



def run_bot_thread():

    asyncio.run(
        start_bot()
    )



def main():

    logger.info("Launching services...")


    # Start telegram bot in background
    bot_thread = threading.Thread(
        target=run_bot_thread,
        daemon=True
    )

    bot_thread.start()



    # Start web server for Render
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )



if __name__ == "__main__":
    main()
