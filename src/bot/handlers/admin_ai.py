import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_ai_keyboard import admin_ai_keyboard
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.states.admin_states import AdminState
from src.core.config.settings import get_settings
from src.services.ai_agent_service import AIAgentError, AIAgentService

router = Router()
settings = get_settings()
agent = AIAgentService()


def _owner(user_id: int) -> bool:
    return bool(settings.OWNER_ID) and user_id == settings.OWNER_ID


def _chunk(text: str, size: int = 3900) -> list[str]:
    text = text or ""
    if len(text) <= size:
        return [text]
    return [text[i : i + size] for i in range(0, len(text), size)]


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    for secret in (settings.effective_ai_api_key, settings.GITHUB_TOKEN, settings.BOT_TOKEN):
        if secret:
            text = text.replace(secret, "***")
    return text[:1200]


@router.callback_query(F.data == "admin_ai")
async def ai_home(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "🧠 AI Developer Agent\n\n"
        "دستیار امن توسعه RahYar آماده است.\n\n"
        "💬 مشاوره: سؤال معماری و کدنویسی\n"
        "🔎 Audit: بررسی پروژه\n"
        "🛠 Debug: تحلیل خطا بدون تغییر کد\n"
        "🐞 Fix / ✨ Feature: تغییر فقط روی ai/* و PR\n\n"
        "🔐 کلیدها و فایل‌های حساس نباید داخل پیام‌ها ارسال شوند.\n"
        "⛔️ Merge مستقیم به main توسط Agent انجام نمی‌شود.",
        reply_markup=admin_ai_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "ai_status")
async def ai_status(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    try:
        raw = await asyncio.to_thread(agent.status)
        lines = []
        for line in raw.splitlines():
            if line.startswith("base_url="):
                lines.append("provider=Configured (endpoint hidden)")
            elif line.startswith("repo="):
                lines.append("repository=Configured")
            elif line.startswith("chat_key_configured="):
                lines.append(line)
            else:
                lines.append(line)
        result = "\n".join(lines)
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
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
        result = f"❌ {_safe_error(exc)}"
    for part in _chunk(f"🔎 AI Audit\n\n{result}"):
        await callback.message.answer(part)


@router.callback_query(F.data == "ai_assistant")
async def ai_assistant_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_consult)
    await state.update_data(ai_consult_mode="assistant")
    await callback.message.answer(
        "💬 دستیار کدنویسی فعال شد.\n\n"
        "سؤال فنی بپرسید.\n"
        "⚠️ API key، BOT_TOKEN، DATABASE_URL یا فایل .env را ارسال نکنید.\n\n"
        "برای خروج: /cancel یا 🛑 توقف",
        reply_markup=admin_back_button("admin_ai"),
    )
    await callback.answer()


@router.callback_query(F.data == "ai_debug")
async def ai_debug_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_consult)
    await state.update_data(ai_consult_mode="debug")
    await callback.message.answer(
        "🛠 حالت دیباگ فعال شد.\n\n"
        "لاگ یا خطا را بفرستید. کلیدها و اطلاعات حساس را حذف کنید.\n"
        "این حالت فقط تحلیل می‌کند و فایل را تغییر نمی‌دهد.",
        reply_markup=admin_back_button("admin_ai"),
    )
    await callback.answer()


@router.message(AdminState.waiting_ai_consult, F.text == "/cancel")
async def ai_consult_cancel(message: Message, state: FSMContext):
    if not _owner(message.from_user.id):
        return
    await state.clear()
    await message.answer("گفتگو با Agent بسته شد.", reply_markup=admin_ai_keyboard())


@router.message(AdminState.waiting_ai_consult)
async def ai_consult_message(message: Message, state: FSMContext):
    if not _owner(message.from_user.id):
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("پیام خالی است. سؤال یا لاگ را بفرستید.")
        return
    if len(text) > 8000:
        await message.answer("❌ پیام خیلی طولانی است. لطفاً آن را کوتاه‌تر کنید.")
        return

    data = await state.get_data()
    mode = data.get("ai_consult_mode", "assistant")
    if mode == "debug":
        prompt = (
            "You are debugging the RahYar Academy Telegram bot.\n"
            "Do not modify files. Do not request or expose secrets.\n"
            "Give: root cause, exact paths, concrete fix steps, tests.\n"
            "Answer in Persian; paths/symbols in English.\n\n"
            f"OWNER INPUT:\n{text}"
        )
        header = "🛠 نتیجه دیباگ"
    else:
        prompt = (
            "You are the owner's coding assistant for RahYar.\n"
            "Answer using repository architecture. Do not modify files or expose secrets.\n"
            "Answer in Persian; paths in English.\n\n"
            f"OWNER QUESTION:\n{text}"
        )
        header = "💬 دستیار کدنویسی"

    await message.answer("⏳ در حال پردازش...")
    try:
        result = await asyncio.to_thread(agent.analyze, prompt)
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    for part in _chunk(f"{header}\n\n{result}"):
        await message.answer(part)
    await message.answer("برای سؤال بعدی پیام بدهید یا /cancel بزنید.", reply_markup=admin_ai_keyboard())


@router.callback_query(F.data == "ai_fix")
async def ai_fix_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_task)
    await state.update_data(ai_task_type="fix")
    await callback.message.answer(
        "🐞 باگ را توضیح بدهید.\n\n"
        "🔐 Agent فقط روی branch با پیشوند ai/* کار می‌کند.\n"
        "🧪 تست‌ها قبل از PR اجرا می‌شوند.\n"
        "⛔️ merge به main خودکار نیست."
    )
    await callback.answer()


@router.callback_query(F.data == "ai_feature")
async def ai_feature_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_task)
    await state.update_data(ai_task_type="feature")
    await callback.message.answer(
        "✨ Feature را توضیح بدهید.\n\n"
        "Agent plan → code → tests → PR را انجام می‌دهد.\n"
        "برای write mode باید AI_AGENT_WRITE_ENABLED=true و GitHub token امن تنظیم شده باشد."
    )
    await callback.answer()


@router.message(AdminState.waiting_ai_task)
async def ai_task(message: Message, state: FSMContext):
    if not _owner(message.from_user.id):
        return
    task = (message.text or "").strip()
    if not task:
        await message.answer("❌ توضیح Task خالی است.")
        return
    if len(task) > 8000:
        await message.answer("❌ Task خیلی طولانی است. لطفاً خلاصه‌تر توضیح دهید.")
        return
    data = await state.get_data()
    task_type = data.get("ai_task_type", "feature")
    await state.clear()
    await message.answer(f"🧠 Agent شروع کرد ({task_type})...\n⏳ بررسی → تغییر → تست → PR")
    try:
        result = await asyncio.to_thread(agent.implement, task, task_type)
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    for part in _chunk(result):
        await message.answer(part)


@router.callback_query(F.data == "ai_stop")
async def ai_stop(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.clear()
    await callback.answer("🛑 حالت گفتگو متوقف شد.", show_alert=True)
    try:
        await callback.message.edit_text(
            "🧠 AI Developer Agent\n\nآماده. یکی از گزینه‌ها را انتخاب کنید.",
            reply_markup=admin_ai_keyboard(),
        )
    except Exception:
        await callback.message.answer("🧠 AI Developer Agent آماده است.", reply_markup=admin_ai_keyboard())
