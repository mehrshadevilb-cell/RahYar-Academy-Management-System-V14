import asyncio
import os
from threading import Thread

from fastapi import FastAPI
import uvicorn

from core.logging.logger import logger


app = FastAPI(
    title="RahYar Academy Management System",
    version="14.0"
)


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "RahYar Bot"
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }


def run_web():
    port = int(os.environ.get("PORT", 10000))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )


async def start_bot():

    logger.info("Starting RahYar Bot...")

    from bot.bot import bot_start

    await bot_start()


def main():

    # Render Web Service needs an open port
    web_thread = Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()


    # Start Telegram Bot
    asyncio.run(
        start_bot()
    )


if __name__ == "__main__":
    main()
