import asyncio
import threading

from fastapi import FastAPI
import uvicorn

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
        "service": "RahYar Bot"
    }


@app.get("/health")
async def health():
    return {
        "ok": True
    }



async def start_bot():

    logger.info("Starting RahYar Bot...")

    setup_handlers()

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )



def run_web():

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
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
