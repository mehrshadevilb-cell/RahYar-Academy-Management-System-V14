import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from loguru import logger


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(
            b'{"status":"ok","service":"RahYar Bot"}'
        )

    def log_message(self, format, *args):
        return


def start_health_server():
    """
    Render Web Service needs an open port.
    """
    import os

    port = int(os.environ.get("PORT", 10000))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    logger.info(f"Health server running on port {port}")

    server.serve_forever()


async def start_bot():

    logger.info("Starting RahYar Bot...")

    try:
        # Try different possible bot entry points
        from src.bot import bot_start

        await bot_start()

    except ImportError:

        try:
            from src.bot.main import bot_start

            await bot_start()

        except ImportError:

            try:
                from src.bot.runner import run

                await run()

            except ImportError as e:
                logger.exception(
                    "Bot entry point not found"
                )
                raise e


async def main_async():

    # Start Render health server
    threading.Thread(
        target=start_health_server,
        daemon=True
    ).start()


    # Start Telegram bot
    await start_bot()



def main():

    logger.info(
        "RahYar Application Starting..."
    )

    asyncio.run(
        main_async()
    )


if __name__ == "__main__":
    main()
