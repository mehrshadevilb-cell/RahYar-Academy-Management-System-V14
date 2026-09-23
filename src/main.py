import asyncio
import os
import threading
import traceback
import hashlib
import hmac
import base64
import json
import time
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
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
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


def _telegram_webapp_secret(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def _sign_web_session(user_id: int, telegram_id: str) -> str:
    payload = f"{user_id}:{telegram_id}:{int(time.time())}"
    secret = (settings.SECRET_KEY or settings.WEB_STUDENT_BRIDGE_SECRET or settings.BOT_TOKEN).encode()
    signature = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode().rstrip("=")


def _verify_web_session(value: str | None) -> tuple[int, str] | None:
    if not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()
        user_id, telegram_id, issued_at, signature = raw.split(":", 3)
        payload = f"{user_id}:{telegram_id}:{issued_at}"
        secret = (settings.SECRET_KEY or settings.WEB_STUDENT_BRIDGE_SECRET or settings.BOT_TOKEN).encode()
        expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        if int(time.time()) - int(issued_at) > 30 * 24 * 60 * 60:
            return None
        return int(user_id), telegram_id
    except (TypeError, ValueError, UnicodeError):
        return None


def _validate_telegram_init_data(init_data: str) -> dict:
    bot_token = (settings.BOT_TOKEN or "").strip()
    if not bot_token:
        raise ValueError("bot_token_not_configured")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    auth_date = int(pairs.get("auth_date", "0"))
    if not received_hash or not auth_date:
        raise ValueError("missing_hash_or_auth_date")
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
    calculated_hash = hmac.new(
        _telegram_webapp_secret(bot_token),
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("invalid_hash")
    max_age = int(os.getenv("TELEGRAM_WEBAPP_AUTH_MAX_AGE_SECONDS", "86400"))
    if int(time.time()) - auth_date > max_age:
        raise ValueError("expired_init_data")
    return pairs


@app.post("/api/v1/telegram/webapp-auth")
async def telegram_webapp_auth(request: Request):
    body = await request.json()
    init_data = str(body.get("initData") or "").strip()
    if not init_data:
        return JSONResponse({"ok": False, "error": "telegram_init_data_required"}, status_code=400)

    try:
        pairs = _validate_telegram_init_data(init_data)
        tg_user = json.loads(pairs.get("user", "{}"))
        telegram_id = str(tg_user.get("id") or "")
        if not telegram_id:
            raise ValueError("telegram_user_missing")

        full_name = " ".join(
            part for part in (tg_user.get("first_name"), tg_user.get("last_name")) if part
        ).strip() or "هنرجو"
        username = (tg_user.get("username") or "").strip() or None

        db = SessionLocal()
        try:
            from src.services.canonical_identity_service import CanonicalIdentityService
            identity = CanonicalIdentityService()
            user = identity.link_telegram_account(
                db,
                telegram_id=telegram_id,
                full_name=full_name,
                username=username,
            )
            if not user.is_active:
                return JSONResponse({"ok": False, "error": "user_inactive"}, status_code=403)

            response = JSONResponse({
                "ok": True,
                "user": {
                    "id": str(user.id),
                    "studentNumber": f"RH{user.id:06d}",
                    "username": user.phone or username or f"tg_{telegram_id}",
                    "fullName": user.full_name,
                    "phone": user.phone,
                    "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                    "telegramLinked": True,
                    "telegramId": telegram_id,
                },
            })
            response.set_cookie(
                "rahyar_session",
                _sign_web_session(user.id, telegram_id),
                max_age=30 * 24 * 60 * 60,
                httponly=True,
                secure=True,
                samesite="lax",
                path="/",
            )
            return response
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Telegram Mini App auth rejected: %s", exc)
        return JSONResponse({"ok": False, "error": "invalid_telegram_init_data"}, status_code=401)


@app.get("/api/v1/telegram/me")
async def telegram_webapp_me(request: Request):
    session = _verify_web_session(request.cookies.get("rahyar_session"))
    if not session:
        return JSONResponse({"ok": False, "error": "not_authenticated"}, status_code=401)
    user_id, telegram_id = session
    db = SessionLocal()
    try:
        account = db.query(TelegramAccount).filter(TelegramAccount.telegram_id == telegram_id).first()
        if not account or account.user_id != user_id or not account.user.is_active:
            return JSONResponse({"ok": False, "error": "session_invalid"}, status_code=401)
        user = account.user
        return JSONResponse({"ok": True, "user": {
            "id": str(user.id),
            "studentNumber": f"RH{user.id:06d}",
            "fullName": user.full_name,
            "phone": user.phone,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "telegramId": telegram_id,
            "telegramLinked": True,
        }})
    finally:
        db.close()


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


async def _run_bot_polling() -> None:
    if not bot_enabled:
        logger.warning("Telegram polling disabled; web/API will continue running")
        return
    try:
        logger.info("Starting Telegram polling")
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        raise
    except (TelegramConflictError, TelegramUnauthorizedError):
        logger.exception("Telegram polling stopped because the bot token/session is unavailable")
    except Exception:
        logger.exception("Telegram polling stopped unexpectedly")


def _initialize_application() -> None:
    """Run synchronous bootstrapping before the async web/bot loops start."""
    setup_handlers()
    ensure_critical_schema()

    seed_default_card()
    seed_default_products()
    seed_default_online_courses()

    db = SessionLocal()
    try:
        try:
            result = auto_configure_ai(db)
            logger.info("AI auto-configuration completed: %s", result)
        except Exception:
            db.rollback()
            logger.exception("AI auto-configuration failed; application will continue")
    finally:
        db.close()


async def _serve() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    server = uvicorn.Server(config)

    reminder_scheduler = InstallmentReminderScheduler(bot)
    artistyar_scheduler = ArtistYarPracticeReminderScheduler(bot)
    model_refresh_scheduler = AIModelRefreshScheduler()

    reminder_scheduler.start()
    artistyar_scheduler.start()
    model_refresh_scheduler.start()
    bot_task = asyncio.create_task(_run_bot_polling(), name="telegram-polling")

    try:
        logger.info("Starting RahYar web server on %s:%s", host, port)
        await server.serve()
    finally:
        for scheduler in (
            reminder_scheduler,
            artistyar_scheduler,
            model_refresh_scheduler,
        ):
            scheduler.stop()

        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass

        try:
            await bot.session.close()
        except Exception:
            logger.exception("Failed to close Telegram bot session")


def main() -> None:
    _initialize_application()
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
