import asyncio
import os
import threading
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
import uvicorn

from src.bot.bot import bot, dp, setup_handlers, ai_agent_knowledge
from src.core.config.settings import get_settings
from src.core.logging.logger import get_logger
from src.database.seed_payment_card import seed_default_card
from src.database.seed_products import seed_default_products
from src.database.seed_online_courses import seed_default_online_courses
from src.database.session import SessionLocal
from src.services.ai.auto_configure import auto_configure_ai
from src.services.reminder_scheduler import InstallmentReminderScheduler
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


app = FastAPI(title="RahYar Academy Management System", description="Telegram bot + public sales website sharing one database")
app.include_router(storefront_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "path": request.url.path, "error_type": type(exc).__name__, "error": str(exc)[:500]})


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return JSONResponse({"ok": True, "build": _build_id()})


@app.api_route("/", methods=["HEAD"])
async def head_root():
    return Response(status_code=200)


@app.get("/api/status")
async def api_status():
    return JSONResponse({"status": "running", "service": "RahYar Bot + Web", "site": settings.SITE_NAME, "build": _build_id(), "chat_assistant": settings.CHAT_ASSISTANT_ENABLED, "knowledge": settings.KNOWLEDGE_ENABLED, "ai_agent_knowledge_runtime": True})


@app.get("/api/debug-storefront")
async def debug_storefront():
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
        # AI providers are optional. The bot must still boot when no provider key
        # is configured or a third-party gateway is temporarily unavailable.
        logger.exception("AI auto-configuration failed; continuing startup")


async def start_bot():
    logger.info("Starting RahYar Bot... build=%s", _build_id())
    seed_default_card()
    seed_default_products()
    seed_default_online_courses()
    await _auto_configure_ai_at_startup()
    setup_handlers()
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Telegram webhook cleared; starting long-polling")
    except Exception:
        logger.exception("Failed to delete Telegram webhook; continuing to poll")

    installment_scheduler = InstallmentReminderScheduler(bot)
    installment_scheduler.start()
    ai_agent_knowledge.start()

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=False)
    finally:
        await ai_agent_knowledge.stop()
        if installment_scheduler._task:
            installment_scheduler._task.cancel()
        await bot.session.close()


def run_web():
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


async def main():
    logger.info("Booting application... build=%s", _build_id())
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    await start_bot()


if __name__ == "__main__":
    asyncio.run(main())
