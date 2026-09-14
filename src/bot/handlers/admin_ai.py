import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_ai_keyboard import admin_ai_keyboard
from src.bot.states.admin_states import AdminState
from src.core.config.settings import get_settings
from src.services.ai_agent_service import AIAgentError, AIAgentService

router = Router()
settings = get_settings()
agent = AIAgentService()


def _owner(user_id: int) -> bool:
    return bool(settings.OWNER_ID) and user_id == settings.OWNER_ID


@router.callback_query(F.data == "admin_ai")
async def ai_home(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await callback.message.edit_text("🧠 AI Developer Agent\n\nکنترل تعمیر، Audit و توسعه پروژه:", reply_markup=admin_ai_keyboard())
    await callback.answer()


@router.callback_query(F.data == "ai_status")
async def ai_status(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    try:
        result = await asyncio.to_thread(agent.status)
    except AIAgentError as exc:
        result = f"❌ {exc}"
    await callback.message.answer(f"🧠 Agent status\n\n{result}")
    await callback.answer()


@router.callback_query(F.data == "ai_analyze")
async def ai_analyze(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.answer("در حال Audit...", show_alert=False)
    try:
        result = await asyncio.to_thread(agent.analyze)
    except AIAgentError as exc:
        result = f"❌ {exc}"
    await callback.message.answer(f"🔎 AI Audit\n\n{result[:3900]}")


@router.callback_query(F.data == "ai_fix")
async def ai_fix_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_task)
    await state.update_data(ai_task_type="fix")
    await callback.message.answer("🐞 مشکل/باگ را دقیق توضیح بدهید. Agent روی branch جدا کار می‌کند و قبل از commit تست می‌گیرد.")
    await callback.answer()


@router.callback_query(F.data == "ai_feature")
async def ai_feature_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_task)
    await state.update_data(ai_task_type="feature")
    await callback.message.answer("✨ Feature موردنظر را دقیق توضیح بدهید. Agent فقط روی branch ai/* کار می‌کند.")
    await callback.answer()


@router.message(AdminState.waiting_ai_task)
async def ai_task(message: Message, state: FSMContext):
    if not _owner(message.from_user.id):
        return
    task = (message.text or "").strip()
    if not task:
        await message.answer("❌ توضیح Task خالی است.")
        return
    await state.clear()
    await message.answer("🧠 Agent شروع کرد...\n⏳ کد را بررسی، تغییر و تست می‌کند.")
    try:
        result = await asyncio.to_thread(agent.implement, task)
    except AIAgentError as exc:
        result = f"❌ {exc}"
    await message.answer(result[:3900])


@router.callback_query(F.data == "ai_stop")
async def ai_stop(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.answer("🛑 اجرای خودکار جدید فقط با اجرای مجدد Task شروع می‌شود.", show_alert=True)
