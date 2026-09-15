import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_ai_keyboard import admin_ai_keyboard
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.states.admin_states import AdminState
from src.core.config.settings import get_settings
from src.services.ai_agent_runtime import runtime
from src.services.ai_agent_service import AIAgentError

router = Router()
settings = get_settings()


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


def _home_text() -> str:
    return (
        "🤖 <b>RahYar AI Developer</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🟢 API: آماده بررسی\n"
        "🧠 Planner: فعال\n"
        "🔐 Security: محافظت‌شده\n"
        "📂 Repository: متصل\n\n"
        "برای شروع یک عملیات انتخاب کنید.\n"
        "<i>Write taskها → Plan → Code → Test → PR</i>"
    )


@router.callback_query(F.data == "admin_ai")
async def ai_home(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(_home_text(), reply_markup=admin_ai_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ai_status")
async def ai_status(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    try:
        raw = await asyncio.to_thread(runtime.agent.status)
        lines = []
        for line in raw.splitlines():
            if line.startswith("base_url="):
                lines.append("provider=Configured (endpoint hidden)")
            elif line.startswith("repo="):
                lines.append("repository=Configured")
            elif line.startswith("provider_ping="):
                ping = line.removeprefix("provider_ping=")
                lines.append(f"api_test={ping[:300]}")
            else:
                lines.append(line)
        result = "\n".join(lines)
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    await callback.message.answer(f"🧪 <b>AI API / Agent Status</b>\n\n<code>{result}</code>", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ai_test_models")
async def ai_test_models(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.answer("🧪 در حال تست زنده همه مدل‌ها...", show_alert=False)
    try:
        result = await asyncio.to_thread(runtime.agent.test_provider_models)
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    for part in _chunk(result):
        await callback.message.answer(part, parse_mode="HTML")


@router.callback_query(F.data == "ai_security")
async def ai_security(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    text = (
        "🔐 <b>Security Guardrails</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ owner-only controls\n"
        "✅ protected paths / secrets blocked\n"
        "✅ HTTPS provider endpoint\n"
        "✅ ai/* branch isolation\n"
        "✅ compile + pytest gate\n"
        "✅ no automatic merge to main\n"
        "✅ bounded retries\n"
        "✅ Telegram errors redact configured secrets\n"
        "\n⚠️ اطلاعات حساس را داخل پیام Task یا لاگ ارسال نکنید."
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ai_task_status")
async def ai_task_status(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    if runtime.active(callback.from_user.id):
        label = runtime.active_label(callback.from_user.id) or "task"
        await callback.answer(f"🟡 Task فعال است: {label}", show_alert=True)
    else:
        await callback.answer("🟢 Task فعالی وجود ندارد.", show_alert=True)


@router.callback_query(F.data == "ai_analyze")
async def ai_analyze(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.answer("در حال Audit...", show_alert=False)
    try:
        result = await asyncio.to_thread(runtime.agent.analyze)
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    for part in _chunk(f"🔎 <b>AI Audit</b>\n\n{result}"):
        await callback.message.answer(part, parse_mode="HTML")


@router.callback_query(F.data == "ai_assistant")
async def ai_assistant_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_consult)
    await state.update_data(ai_consult_mode="assistant")
    await callback.message.answer(
        "💬 <b>Assistant</b>\n\nسؤال فنی بپرسید. Agent با context پروژه پاسخ می‌دهد.\n\n"
        "⚠️ API key، BOT_TOKEN، DATABASE_URL یا .env را ارسال نکنید.\n"
        "برای خروج: /cancel",
        reply_markup=admin_back_button("admin_ai"),
        parse_mode="HTML",
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
        "🐞 <b>Debug</b>\n\nلاگ یا خطا را بفرستید. این حالت فقط تحلیل می‌کند و کد را تغییر نمی‌دهد.\n"
        "کلیدها و اطلاعات حساس را حذف کنید.",
        reply_markup=admin_back_button("admin_ai"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminState.waiting_ai_consult, F.text == "/cancel")
async def ai_consult_cancel(message: Message, state: FSMContext):
    if not _owner(message.from_user.id):
        return
    await state.clear()
    await message.answer("🟢 حالت گفتگو بسته شد.", reply_markup=admin_ai_keyboard())


@router.message(AdminState.waiting_ai_consult)
async def ai_consult_message(message: Message, state: FSMContext):
    if not _owner(message.from_user.id):
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("پیام خالی است.")
        return
    if len(text) > 8000:
        await message.answer("❌ پیام خیلی طولانی است. کوتاه‌تر ارسال کنید.")
        return
    data = await state.get_data()
    mode = data.get("ai_consult_mode", "assistant")
    prompt = (
        "You are the owner's coding assistant for RahYar. Use repository architecture and skills. "
        "Do not modify files or expose secrets. Answer in Persian; paths/symbols in English.\n\n"
        + ("DEBUG MODE: give root cause, exact paths, fix steps and tests.\n" if mode == "debug" else "")
        + f"OWNER INPUT:\n{text}"
    )
    await message.answer("⏳ در حال تحلیل...")
    try:
        result = await asyncio.to_thread(runtime.agent.analyze, prompt)
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    for part in _chunk(f"{'🐞' if mode == 'debug' else '💬'} نتیجه\n\n{result}"):
        await message.answer(part)


@router.callback_query(F.data == "ai_fix")
async def ai_fix_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_task)
    await state.update_data(ai_task_type="fix")
    await callback.message.answer(
        "🐞 <b>Fix Task</b>\n\nباگ را دقیق توضیح بدهید.\n"
        "Agent ابتدا Plan می‌سازد، سپس روی ai/* تغییر می‌دهد، تست می‌کند و در صورت موفقیت PR می‌سازد.",
        parse_mode="HTML",
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
        "✨ <b>Feature Task</b>\n\nقابلیت را با رفتار مورد انتظار توضیح بدهید.\n"
        "Agent → Planner → Skills → Code → Tests → PR",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminState.waiting_ai_task)
async def ai_task(message: Message, state: FSMContext):
    if not _owner(message.from_user.id):
        return
    task = (message.text or "").strip()
    if not task:
        await message.answer("❌ Task خالی است.")
        return
    if len(task) > 8000:
        await message.answer("❌ Task خیلی طولانی است. کوتاه‌تر توضیح دهید.")
        return
    data = await state.get_data()
    task_type = data.get("ai_task_type", "feature")
    await state.clear()

    async def progress(text: str) -> None:
        await message.answer(text)

    await message.answer(
        "🛠 <b>Task Started</b>\n━━━━━━━━━━━━━━━━━━\n"
        "🟡 وضعیت: در حال پردازش\n🔐 فقط owner\n🌿 branch: ai/*",
        parse_mode="HTML",
    )
    try:
        result = await runtime.run_write(message.from_user.id, task, task_type, progress)
    except asyncio.CancelledError:
        await message.answer("🛑 Task لغو شد. تغییرات ناقص commit/PR نمی‌شوند.")
        return
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    for part in _chunk(result):
        await message.answer(part)
    await message.answer("🤖 Agent آماده Task بعدی است.", reply_markup=admin_ai_keyboard())


@router.callback_query(F.data == "ai_stop")
async def ai_stop(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    cancelled = await runtime.cancel(callback.from_user.id)
    await state.clear()
    if cancelled:
        await callback.answer("🛑 Task واقعاً لغو شد.", show_alert=True)
    else:
        await callback.answer("🟢 Task فعالی وجود نداشت.", show_alert=True)
    try:
        await callback.message.edit_text(_home_text(), reply_markup=admin_ai_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(_home_text(), reply_markup=admin_ai_keyboard(), parse_mode="HTML")
