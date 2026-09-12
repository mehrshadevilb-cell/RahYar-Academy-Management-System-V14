import asyncio
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from loguru import logger


# ==========================
# Render Health Check Server
# ==========================

PORT = int(os.environ.get("PORT", 10000))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(
                b'{"status":"ok","service":"RahYar Bot"}'
            )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def start_health_server():
    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    logger.info(f"Health server running on port {PORT}")

    server.serve_forever()



# ==========================
# Bot Startup
# ==========================

async def start_bot():

    logger.info("Starting RahYar Bot...")

    # این قسمت باید همان کد قبلی خودت باشد
    # مثال:
    #
    # await bot.start()
    #
    # یا:
    #
    # application.run_polling()

    from src.bot import run_bot

    await run_bot()



# ==========================
# Main
# ==========================

def main():

    # Render نیاز دارد پورت باز باشد
    threading.Thread(
        target=start_health_server,
        daemon=True
    ).start()


    try:
        asyncio.run(start_bot())

    except KeyboardInterrupt:
        logger.info("Bot stopped")

    except Exception as e:
        logger.exception(e)
        raise



if __name__ == "__main__":
    main()
