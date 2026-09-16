import asyncio
import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_ai_keyboard import admin_ai_keyboard
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.states.admin_states import AdminState
from src.core.admin_access import is_admin_user
from src.core.config.settings import get_settings
from src.services.ai_agent_runtime import runtime
from src.services.ai_agent_service import AIAgentError

router = Router()
settings = get_settings()

# Only surface "در حال تحلیل" when the model is genuinely slow.
_SLOW_RESPONSE_SECONDS = 1.5


def _owner(user_id: int, username: str | None = None) -> bool:
    return is_admin_user(user_id, username)


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


def _safe_html(text: str) -> str:
    """Escape model and runtime output before embedding it in Telegram HTML."""
    return html.escape(text or "", quote=False)


AUDIT_PROFILES = {
    "full": "Audit the entire repository for correctness, security, reliability, data integrity, UX and test gaps.",
    "security": "Audit only security, authentication, authorization, secrets, privacy, injection and data exposure risks.",
    "reliability": "Audit provider failover, background tasks, error handling, retries, migrations and operational reliability.",
}


def audit_request(profile: str = "full") -> str:
    selected = AUDIT_PROFILES.get(profile, AUDIT_PROFILES["full"])
    return (
        f"{selected}\n"
        "Return an evidence-based prioritized report. Include confirmed findings, "
        "needs-verification items, severity, exact paths/symbols, impact, smallest safe fix, "
        "and a regression test for each finding. End with counts and next action."
    )


def debug_request(user_input: str) -> str:
    return (
        "DEBUG MODE: Analyze only; do not modify files or propose unverified facts.\n"
        "Return exactly these sections:\n"
        "1. INCIDENT SUMMARY\n2. REPRODUCTION / MISSING DATA\n3. ROOT CAUSE HYPOTHESES "
        "(ranked with confidence)\n4. EVIDENCE (exact repository paths/symbols)\n"
        "5. SAFE FIX STEPS\n6. REGRESSION TESTS\n7. ROLLBACK / RISK NOTES\n"
        "If evidence is insufficient, say what to collect next. Never request secrets.\n\n"
        f"OWNER DEBUG INPUT:\n{user_input}"
    )


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


async def _run_with_optional_progress(message: Message, work_coro):
    """Await work; only send progress text if it takes longer than the threshold."""
    task = asyncio.create_task(work_coro)
    progress_msg: Message | None = None
    try:
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=_SLOW_RESPONSE_SECONDS)
        except asyncio.TimeoutError:
            progress_msg = await message.answer("⏳ در حال تحلیل...")
            return await task
    finally:
        if progress_msg is not None:
            try:
                await progress_msg.delete()
            except Exception:
                pass


@router.callback_query(F.data == "admin_ai")
async def ai_home(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(_home_text(), reply_markup=admin_ai_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ai_status")
async def ai_status(callback: CallbackQuery):
    if not _owner(callback.from_user.id, callback.from_user.username):
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
    await callback.message.answer(
        f"🧪 <b>AI API / Agent Status</b>\n\n<code>{_safe_html(result)}</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "ai_test_models")
async def ai_test_models(callback: CallbackQuery):
    if not _owner(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.answer("🧪 در حال تست زنده همه مدل‌ها...", show_alert=False)
    try:
        result = await asyncio.to_thread(runtime.agent.test_provider_models)
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    for part in _chunk(result):
        await callback.message.answer(_safe_html(part), parse_mode="HTML")


@router.callback_query(F.data == "ai_security")
async def ai_security(callback: CallbackQuery):
    if not _owner(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔️", show_alert=True)
        return
    text = (
        "🔐 <b>Security Guardrails</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ owner/admin-only controls\n"
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
    if not _owner(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔️", show_alert=True)
        return
    if runtime.active(callback.from_user.id):
        label = runtime.active_label(callback.from_user.id) or "task"
        await callback.answer(f"🟡 Task فعال است: {label}", show_alert=True)
    else:
        await callback.answer("🟢 Task فعالی وجود ندارد.", show_alert=True)


@router.callback_query(F.data.startswith("ai_analyze:"))
async def ai_analyze(callback: CallbackQuery):
    if not _owner(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.answer("در حال Audit...", show_alert=False)
    try:
        profile = callback.data.rsplit(":", 1)[-1]
        result = await asyncio.to_thread(runtime.agent.analyze, audit_request(profile))
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    for index, part in enumerate(_chunk(result)):
        heading = "🔎 <b>AI Audit</b>\n\n" if index == 0 else ""
        await callback.message.answer(heading + _safe_html(part), parse_mode="HTML")


@router.callback_query(F.data == "ai_assistant")
async def ai_assistant_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id, callback.from_user.username):
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
    if not _owner(callback.from_user.id, callback.from_user.username):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_consult)
    await state.update_data(ai_consult_mode="debug")
    await callback.message.answer(
        "🐞 <b>Debug</b>\n\nلاگ یا خطا را بفرستید. این حالت فقط تحلیل می‌کند و کد را تغییر نمی‌دهد.\n"
        "برای نتیجه بهتر این موارد را بنویسید: رفتار فعلی، رفتار مورد انتظار، مراحل بازتولید، زمان شروع مشکل و مسیر مربوطه.\n"
        "کلیدها و اطلاعات حساس را حذف کنید.",
        reply_markup=admin_back_button("admin_ai"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminState.waiting_ai_consult, F.text == "/cancel")
async def ai_consult_cancel(message: Message, state: FSMContext):
    if not _owner(message.from_user.id, message.from_user.username):
        return
    await state.clear()
    await message.answer("🟢 حالت گفتگو بسته شد.", reply_markup=admin_ai_keyboard())


@router.message(AdminState.waiting_ai_consult)
async def ai_consult_message(message: Message, state: FSMContext):
    if not _owner(message.from_user.id, message.from_user.username):
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
        + (debug_request(text) if mode == "debug" else f"OWNER INPUT:\n{text}")
    )
    try:
        result = await _run_with_optional_progress(
            message,
            asyncio.to_thread(runtime.agent.analyze, prompt),
        )
    except AIAgentError as exc:
        result = f"❌ {_safe_error(exc)}"
    for part in _chunk(f"{'🐞' if mode == 'debug' else '💬'} نتیجه\n\n{result}"):
        await message.answer(part)


@router.callback_query(F.data == "ai_fix")
async def ai_fix_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id, callback.from_user.username):
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
    if not _owner(callback.from_user.id, callback.from_user.username):
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
    if not _owner(message.from_user.id, message.from_user.username):
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
        "🟡 وضعیت: در حال پردازش\n🔐 فقط owner/admin\n🌿 branch: ai/*",
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
    if not _owner(callback.from_user.id, callback.from_user.username):
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
