from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.types import CallbackQuery

from src.core.admin_access import is_admin_user
from src.core.config.settings import get_settings
from src.services.ai_agent_runtime import runtime
from src.services.ai_agent_service import AIAgentError

router = Router(name="admin_ai_speed")
settings = get_settings()


def _owner(user_id: int, username: str | None = None) -> bool:
    return is_admin_user(user_id, username)


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    for secret in (settings.effective_ai_api_key, settings.GITHUB_TOKEN, settings.BOT_TOKEN):
        if secret:
            text = text.replace(secret, "***")
    return text[:1200]


@router.callback_query(F.data == "ai_auto_connect")
async def ai_auto_connect(callback: CallbackQuery) -> None:
    if not _owner(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.answer("⚡ در حال انتخاب سریع‌ترین مدل...", show_alert=False)
    try:
        result = await asyncio.to_thread(runtime.agent.auto_connect_working_model)
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    except Exception as exc:
        result = f"❌ {_safe_error(exc)}"
    await callback.message.answer(result, parse_mode="HTML")


@router.callback_query(F.data == "ai_speed_monitor")
async def ai_speed_monitor(callback: CallbackQuery) -> None:
    if not _owner(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.answer("📡 خواندن مانیتور...", show_alert=False)
    try:
        from src.services.ai.model_speed_monitor import model_speed_monitor

        snap = model_speed_monitor.snapshot()
        if not snap.get("tested"):
            snap = await model_speed_monitor.force_probe()
        lines = [
            "📡 <b>Continuous Speed Monitor</b>",
            "━━━━━━━━━━━━━━━━━━",
            f"⚡ Fastest: <code>{snap.get('route') or '—'}</code>",
            f"⏱ Latency: <code>{snap.get('fastest_latency_ms')}ms</code>",
            f"🟢 Working: <b>{snap.get('working', 0)}/{snap.get('tested', 0)}</b>",
        ]
        for row in (snap.get("results") or [])[:15]:
            icon = "🟢" if row.get("ok") else "🔴"
            lines.append(
                f"{icon} <code>{row.get('provider')}/{row.get('model')}</code> · "
                f"{row.get('latency_ms')}ms · {row.get('status')}"
            )
        lines.append(
            "\nℹ️ همه مدل‌ها به‌صورت مداوم تست می‌شوند و Agent به سریع‌ترین پاسخ‌دهنده سوئیچ می‌کند."
        )
        await callback.message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as exc:
        await callback.message.answer(f"❌ {_safe_error(exc)}")
