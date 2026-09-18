import asyncio
import os
import threading
import traceback
import hashlib
import hmac
from urllib.parse import parse_qsl
from pathlib import Path

from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from aiogram.types import MenuButtonWebApp, WebAppInfo
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn

from src.bot.bot import bot, bot_enabled, dp, setup_handlers, ai_agent_knowledge
from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.core.middleware.request_id import RequestIdMiddleware
from src.core.diagnostics.health import build_health_report
from src.database.models.telegram_account import TelegramAccount
from src.database.schema_guard import ensure_critical_schema
from src.database.seed_payment_card import seed_default_card
from src.database.seed_products import seed_default_products
from src.database.seed_online_courses import seed_default_online_courses
from src.database.session import SessionLocal
from src.services.ai.auto_configure import auto_configure_ai
from src.services.ai.model_refresh_scheduler import AIModelRefreshScheduler
from src.services.reminder_scheduler import InstallmentReminderScheduler
from src.services.artistyar_practice_reminder_scheduler import ArtistYarPracticeReminderScheduler
from src.web.api_ai import router as api_ai_router
from src.web.api_v1 import router as api_v1_router
from src.web.router import router as storefront_router

settings = get_settings()
logger = get_logger("rahyar.main")


def _build_id() -> str:
    env_id = (os.getenv("RAHYAR_BUILD_ID") or "").strip()
    if env_id:
        return env_id
    marker = Path("/tmp/rahyar-build-id.txt")
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip() or "unknown"
    local = Path(__file__).resolve().parents[1] / "docker-build-id.txt"
    if local.is_file():
        return local.read_text(encoding="utf-8").strip() or "unknown"
    return "unknown"


app = FastAPI(
    title="RahYar Academy Management System",
    description="Telegram bot + Web + JSON API + AI bridge sharing one database",
)

app.add_middleware(RequestIdMiddleware)

_cors_origins = [o.strip() for o in (os.getenv("CORS_ORIGINS") or "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(storefront_router)
app.include_router(api_v1_router)
app.include_router(api_ai_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    report = await build_health_report(_build_id())
    return JSONResponse(report)


@app.api_route("/", methods=["HEAD"])
async def head_root():
    return Response(status_code=200)


@app.post("/api/v1/telegram/webapp-auth")
async def telegram_webapp_auth(request: Request):
    body = await request.json()
    init_data = str(body.get("initData") or "").strip()
    if not init_data:
        return JSONResponse({"ok": False, "error": "telegram_init_data_required"}, status_code=400)

    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token:
        return JSONResponse({"ok": False, "error": "bot_token_not_configured"}, status_code=503)

    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", "")
        auth_date = int(pairs.get("auth_date", "0"))
        if not received_hash or not auth_date:
            raise ValueError("missing_hash_or_auth_date")
        data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise ValueError("invalid_hash")
        import time
        max_age = int(os.getenv("TELEGRAM_WEBAPP_AUTH_MAX_AGE_SECONDS", "86400"))
        if int(time.time()) - auth_date > max_age:
            raise ValueError("expired_init_data")
        import json
        tg_user = json.loads(pairs.get("user", "{}"))
        telegram_id = str(tg_user.get("id") or "")
        if not telegram_id:
            raise ValueError("telegram_user_missing")

        db = SessionLocal()
        try:
            account = db.query(TelegramAccount).filter(TelegramAccount.telegram_id == telegram_id).first()
            if not account or not account.user or not account.user.is_active:
                return JSONResponse({"ok": False, "error": "telegram_account_not_linked"}, status_code=403)
            user = account.user
            return JSONResponse({
                "ok": True,
                "user": {
                    "id": str(user.id),
                    "username": user.phone or account.username or f"tg_{telegram_id}",
                    "fullName": user.full_name,
                    "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                    "telegramLinked": True,
                    "telegramId": telegram_id,
                },
            })
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Telegram Mini App auth rejected: %s", exc)
        return JSONResponse({"ok": False, "error": "invalid_telegram_init_data"}, status_code=401)


@app.get("/api/status")
async def api_status():
    return JSONResponse({
        "status": "running",
        "service": "RahYar Bot + Web + API v1 + AI bridge",
        "site": settings.SITE_NAME,
        "build": _build_id(),
        "chat_assistant": settings.CHAT_ASSISTANT_ENABLED,
        "knowledge": settings.KNOWLEDGE_ENABLED,
        "ai_agent_knowledge_runtime": True,
        "telegram_polling": bot_enabled,
        "api_v1": True,
        "ai_bridge": True,
    })


@app.get("/api/debug-storefront")
async def debug_storefront():
    if not settings.DEBUG:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    from src.services.web_order_service import WebOrderService
    out: dict = {"ok": True, "build": _build_id(), "steps": []}
    db = SessionLocal()
    try:
        svc = WebOrderService()
        try:
            products = svc.list_products(db)
            out["steps"].append({"list_products": "ok", "count": len(products)})
        except Exception as exc:
            out["ok"] = False
            out["steps"].append({"list_products": "fail", "error_type": type(exc).__name__, "error": str(exc)[:400], "trace": traceback.format_exc()[-800:]})
        try:
            classes = svc.list_online_classes(db)
            out["steps"].append({"list_online_classes": "ok", "count": len(classes)})
        except Exception as exc:
            out["ok"] = False
            out["steps"].append({"list_online_classes": "fail", "error_type": type(exc).__name__, "error": str(exc)[:400], "trace": traceback.format_exc()[-800:]})
        try:
            from fastapi.templating import Jinja2Templates
            tpl_dir = Path(__file__).resolve().parent / "web" / "templates"
            out["steps"].append({"templates_dir": str(tpl_dir), "exists": tpl_dir.is_dir(), "files": sorted(p.name for p in tpl_dir.glob("*.html")) if tpl_dir.is_dir() else []})
            templates = Jinja2Templates(directory=str(tpl_dir))
            templates.env.get_template("home.html")
            templates.env.get_template("base.html")
            out["steps"].append({"jinja_home": "ok"})
        except Exception as exc:
            out["ok"] = False
            out["steps"].append({"jinja": "fail", "error_type": type(exc).__name__, "error": str(exc)[:400]})
    finally:
        db.close()
    return JSONResponse(out)


async def _auto_configure_ai_at_startup() -> None:
    def run():
        db = SessionLocal()
        try:
            return auto_configure_ai(db)
        finally:
            db.close()

    try:
        result = await asyncio.to_thread(run)
        logger.info("AI auto-configuration completed: %s", result)
    except Exception:
        logger.exception("AI auto-configuration failed; continuing startup")


async def _prepare_telegram_polling() -> None:
    me = await bot.get_me()
    logger.info("Telegram bot authenticated: @%s (id=%s)", me.username or "unknown", me.id)
    web_app_url = settings.telegram_web_app_url
    if web_app_url:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="سایت آکادمی",
                    web_app=WebAppInfo(url=web_app_url),
                )
            )
            logger.info("Telegram Mini App menu button configured")
        except Exception:
            # Polling must remain available if Telegram rejects a URL before
            # the owner completes BotFather domain configuration.
            logger.exception("Telegram Mini App menu setup failed")
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Telegram webhook cleared; polling can start")


async def _poll_telegram_forever() -> None:
    restart_delay = max(2, int(os.getenv("TELEGRAM_POLLING_RESTART_DELAY_SECONDS", "5")))
    max_delay = max(restart_delay, int(os.getenv("TELEGRAM_POLLING_MAX_RESTART_DELAY_SECONDS", "60")))
    consecutive_failures = 0

    while True:
        try:
            await _prepare_telegram_polling()
            consecutive_failures = 0
            logger.info("Starting Telegram long-polling; build=%s", _build_id())
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                handle_signals=False,
            )
            logger.warning("Telegram polling stopped without an exception; restarting")
            consecutive_failures += 1
        except TelegramUnauthorizedError:
            logger.critical("Telegram bot token is invalid or revoked; polling cannot continue")
            raise
        except TelegramConflictError:
            consecutive_failures += 1
            logger.error(
                "Telegram polling conflict (another getUpdates consumer is active); "
                "retrying after %ss",
                min(max_delay, restart_delay * min(2 ** (consecutive_failures - 1), 8)),
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception:
            consecutive_failures += 1
            logger.exception("Telegram polling crashed; will restart")

        delay = min(max_delay, restart_delay * min(2 ** max(consecutive_failures - 1, 0), 8))
        await asyncio.sleep(delay)


async def start_bot():
    logger.info("Starting RahYar Bot... build=%s", _build_id())
    if not bot_enabled:
        logger.critical("Telegram polling disabled because BOT_TOKEN is invalid")
        return
    try:
        ensure_critical_schema()
        logger.info("schema_guard: critical columns verified")
    except Exception:
        logger.exception("schema_guard failed; bot may hit UndefinedColumn errors")
    seed_default_card()
    seed_default_products()
    seed_default_online_courses()
    await _auto_configure_ai_at_startup()
    setup_handlers()

    installment_scheduler = InstallmentReminderScheduler(bot)
    installment_scheduler.start()
    artistyar_practice_scheduler = ArtistYarPracticeReminderScheduler(bot)
    artistyar_practice_scheduler.start()
    ai_model_refresh_scheduler = AIModelRefreshScheduler()
    ai_model_refresh_scheduler.start()
    ai_agent_knowledge.start()

    try:
        await _poll_telegram_forever()
    finally:
        await ai_agent_knowledge.stop()
        ai_model_refresh_scheduler.stop()
        if installment_scheduler._task:
            installment_scheduler._task.cancel()
        artistyar_practice_scheduler.stop()
        await bot.session.close()


def run_web():
    port = int(os.getenv("PORT", "8000"))
    try:
        ensure_critical_schema()
    except Exception:
        logger.exception("schema_guard failed before web startup")
    uvicorn.run(app, host="0.0.0.0", port=port)


async def main():
    logger.info("Booting application... build=%s", _build_id())
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    await start_bot()


if __name__ == "__main__":
    asyncio.run(main())
