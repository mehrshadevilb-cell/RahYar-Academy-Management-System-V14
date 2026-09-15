from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from src.core.admin_access import is_admin_user
from src.services.ai_agent_runtime import runtime

router = Router(name="admin_ai_self_check")


@router.callback_query(F.data == "ai_self_check")
async def ai_self_check(callback: CallbackQuery) -> None:
    if not is_admin_user(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await callback.answer("🩺 در حال بررسی...", show_alert=False)
    try:
        result = await __import__("asyncio").to_thread(runtime.self_check)
    except Exception as exc:
        result = f"🔴 Self-check failed: {type(exc).__name__}: {str(exc)[:700]}"
    await callback.message.answer(result, parse_mode="HTML")
