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
        "قابلیت‌های فعال:\n"
        "• 💬 کدنویسی / معماری\n"
        "• 🛠 دیباگ با لاگ\n"
        "• 🎨 زیباسازی متن و کیبورد تلگرام\n"
        "• 🌐 جستجوی وب (مستندات عمومی)\n"
        "• 🧩 Skills قابل‌گسترش\n"
        "• 🐞/✨ نوشتن کد روی branch ai/* + PR\n\n"
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


@router.callback_query(F.data == "ai_skills")
async def ai_skills(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    try:
        result = await asyncio.to_thread(agent.list_skills_text)
    except AIAgentError as exc:
        result = f"❌ {exc}"
    for part in _chunk(result):
        await callback.message.answer(part)
    await callback.answer()


@router.callback_query(F.data == "ai_analyze")
async def ai_analyze(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await callback.answer("در حال Audit...", show_alert=False)
    try:
        result = await asyncio.to_thread(agent.analyze, mode="assistant")
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
        "💬 دستیار کدنویسی فعال شد (با Skills کدنویسی + جستجوی وب).\n\n"
        "سؤال فنی بپرسید، مثلاً:\n"
        "• جریان تأیید پرداخت کجاست؟\n"
        "• برای feature جدید چه فایل‌هایی لازم است؟\n"
        "• آخرین الگوی Aiogram 3 برای FSM چیست؟ (جستجوی وب)\n\n"
        "خروج: /cancel یا 🛑 توقف",
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
        "Agent با ساختار مخزن + در صورت نیاز جستجوی وب، علت و راه‌حل می‌دهد.\n\n"
        "خروج: /cancel یا 🛑 توقف",
        reply_markup=admin_back_button("admin_ai"),
    )
    await callback.answer()


@router.callback_query(F.data == "ai_ui_polish")
async def ai_ui_polish_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_consult)
    await state.update_data(ai_consult_mode="ui")
    await callback.message.answer(
        "🎨 حالت زیباسازی UI فعال شد.\n\n"
        "بگویید کدام منو/پیام را می‌خواهید بهتر شود.\n"
        "Agent فقط روی متن فارسی، دکمه‌ها و تجربهٔ کاربری تمرکز می‌کند.\n\n"
        "برای اعمال واقعی روی کد از «🎨 اعمال UI (کد)» استفاده کنید.\n"
        "خروج: /cancel",
        reply_markup=admin_back_button("admin_ai"),
    )
    await callback.answer()


@router.callback_query(F.data == "ai_research")
async def ai_research_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_consult)
    await state.update_data(ai_consult_mode="research")
    await callback.message.answer(
        "🌐 حالت جستجوی وب فعال شد.\n\n"
        "موضوع را بفرستید (مثلاً مستندات Aiogram webhook، SQLAlchemy 2 relationship).\n"
        "Agent از DuckDuckGo جستجو می‌کند و خلاصهٔ عملی می‌دهد.\n\n"
        "خروج: /cancel",
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
    elif mode == "ui":
        prompt = (
            "You are polishing Telegram UX for RahYar Academy.\n"
            "Suggest clearer Persian copy, keyboard layout improvements, "
            "and navigation fixes. Do not change business rules.\n"
            "Reference existing keyboard/handler paths when possible.\n"
            "Answer in Persian.\n\n"
            f"OWNER REQUEST:\n{text[:8000]}"
        )
        header = "🎨 پیشنهاد زیباسازی UI"
    elif mode == "research":
        prompt = (
            "Research the topic using web_search when helpful.\n"
            "Summarize practical guidance for the RahYar stack "
            "(Python, aiogram 3, SQLAlchemy 2, PostgreSQL, Redis, Docker).\n"
            "Cite URLs. Answer in Persian with English paths/APIs.\n\n"
            f"TOPIC:\n{text[:8000]}"
        )
        header = "🌐 نتیجه تحقیق"
    else:
        prompt = (
            "You are the owner's coding assistant for the RahYar Academy codebase.\n"
            "Answer using repository inventory, architecture, and web_search if needed.\n"
            "Be practical: which files, functions, and patterns to use.\n"
            "Do NOT modify files. Do NOT dump secrets.\n"
            "Answer in Persian; keep paths in English.\n\n"
            f"OWNER QUESTION:\n{text[:8000]}"
        )
        header = "💬 دستیار کدنویسی"

    await message.answer("⏳ در حال فکر کردن با API (+ skills/tools)...")
    try:
        result = await asyncio.to_thread(agent.analyze, prompt, mode=mode)
    except TypeError:
        # Backward safety if older service without mode kw is loaded briefly
        try:
            result = await asyncio.to_thread(agent.analyze, prompt)
        except AIAgentError as exc:
            result = f"❌ {exc}"
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


@router.callback_query(F.data == "ai_ui_write")
async def ai_ui_write_start(callback: CallbackQuery, state: FSMContext):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminState.waiting_ai_task)
    await state.update_data(ai_task_type="ui")
    await callback.message.answer(
        "🎨 توضیح دهید کدام بخش UI باید زیباتر/روشن‌تر شود.\n"
        "Agent فقط متن‌ها و کیبوردها را با رعایت قوانین کسب‌وکار تغییر می‌دهد و PR می‌سازد."
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
