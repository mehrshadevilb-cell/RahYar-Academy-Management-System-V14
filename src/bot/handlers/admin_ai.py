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


@router.callback_query(F.data == "admin_ai")
async def ai_home(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️ دسترسی ندارید.", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "🧠 AI Developer Agent\n\n"
        "از همین‌جا با API صحبت کنید:\n"
        "• 💬 دستیار کدنویسی — سؤال معماری / چطور پیاده کنم\n"
        "• 🛠 دیباگ — لاگ یا باگ را بفرستید تا علت و راه‌حل بگوید\n"
        "• 🐞/✨ — در صورت فعال بودن write mode، کد را عوض و PR می‌سازد\n\n"
        "merge به main فقط با تأیید شما در GitHub.",
        reply_markup=admin_ai_keyboard(),
    )
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
        "سؤال فنی بپرسید، مثلاً:\n"
        "• جریان تأیید پرداخت کجاست؟\n"
        "• چطور آپارتمان FSM برای رزرو کار می‌کند؟\n"
        "• برای افزودن فیلد جدید به دوره چه فایل‌هایی لازم است؟\n\n"
        "چند پیام پشت‌سرهم می‌توانید بفرستید.\n"
        "برای خروج: /cancel یا دکمه 🛑 توقف",
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
        "لاگ Render، متن خطا، یا توضیح باگ را بفرستید.\n"
        "Agent با ساختار مخزن علت محتمل، فایل‌ها و راه‌حل پیشنهادی را می‌گوید.\n\n"
        "اگر بخواهید بعداً خودش کد را عوض کند از «🐞 رفع باگ (کد)» استفاده کنید.\n"
        "خروج: /cancel یا 🛑 توقف",
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

    data = await state.get_data()
    mode = data.get("ai_consult_mode", "assistant")

    if mode == "debug":
        prompt = (
            "You are debugging the RahYar Academy Telegram bot in production.\n"
            "The owner pasted logs, stack traces, or a bug description below.\n"
            "Using the repository inventory and architecture:\n"
            "1) Likely root cause\n"
            "2) Exact file paths involved\n"
            "3) Concrete fix steps (code-level)\n"
            "4) What to test after the fix\n"
            "Do NOT modify files. Do NOT invent missing modules.\n"
            "Answer in Persian; keep paths and symbols in English.\n\n"
            f"OWNER INPUT:\n{text[:8000]}"
        )
        header = "🛠 نتیجه دیباگ"
    else:
        prompt = (
            "You are the owner's coding assistant for the RahYar Academy codebase.\n"
            "Answer the question using the repository inventory and architecture.\n"
            "Be practical: which files, functions, and patterns to use.\n"
            "Do NOT modify files. Do NOT dump secrets.\n"
            "Answer in Persian; keep paths in English.\n\n"
            f"OWNER QUESTION:\n{text[:8000]}"
        )
        header = "💬 دستیار کدنویسی"

    await message.answer("⏳ در حال فکر کردن با API...")
    try:
        result = await asyncio.to_thread(agent.analyze, prompt)
    except AIAgentError as exc:
        result = f"❌ {exc}"

    for part in _chunk(f"{header}\n\n{result}"):
        await message.answer(part)

    await message.answer(
        "می‌توانید سؤال بعدی را بفرستید، یا /cancel بزنید.",
        reply_markup=admin_ai_keyboard(),
    )


@router.callback_query(F.data == "ai_fix")
async def ai_fix_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_task)
    await state.update_data(ai_task_type="fix")
    await callback.message.answer(
        "🐞 مشکل/باگ را دقیق توضیح بدهید.\n"
        "اگر write mode فعال باشد، Agent کد را روی branch ai/* عوض می‌کند، "
        "تست می‌گیرد و PR باز می‌کند (نه merge به main)."
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
        "✨ Feature موردنظر را دقیق توضیح بدهید.\n"
        "نیاز به AI_AGENT_WRITE_ENABLED + GITHUB_TOKEN دارد."
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
    data = await state.get_data()
    task_type = data.get("ai_task_type", "feature")
    await state.clear()
    await message.answer(
        f"🧠 Agent شروع کرد ({task_type})...\n"
        "⏳ بررسی، تغییر، تست و در صورت امکان PR."
    )
    try:
        result = await asyncio.to_thread(agent.implement, task, task_type)
    except AIAgentError as exc:
        result = f"❌ {exc}"
    for part in _chunk(result):
        await message.answer(part)


@router.callback_query(F.data == "ai_stop")
async def ai_stop(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.clear()
    await callback.answer("گفتگو/Task متوقف شد.", show_alert=True)
    try:
        await callback.message.edit_text(
            "🧠 AI Developer Agent\n\nآماده. یکی از گزینه‌ها را انتخاب کنید.",
            reply_markup=admin_ai_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            "🧠 AI Developer Agent آماده است.",
            reply_markup=admin_ai_keyboard(),
        )
