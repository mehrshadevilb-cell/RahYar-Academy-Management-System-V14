import asyncio
import os
import threading
import traceback
from pathlib import Path

from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn

from src.bot.bot import bot, dp, setup_handlers, ai_agent_knowledge
from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.core.middleware.request_id import RequestIdMiddleware
from src.database.schema_guard import ensure_critical_schema
from src.database.seed_payment_card import seed_default_card
from src.database.seed_products import seed_default_products
from src.database.seed_online_courses import seed_default_online_courses
from src.database.session import SessionLocal
from src.services.ai.auto_configure import auto_configure_ai
from src.services.reminder_scheduler import InstallmentReminderScheduler
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

_cors_origins = [
    o.strip()
    for o in (os.getenv("CORS_ORIGINS") or "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
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
    return JSONResponse({"ok": True, "build": _build_id()})


@app.api_route("/", methods=["HEAD"])
async def head_root():
    return Response(status_code=200)
