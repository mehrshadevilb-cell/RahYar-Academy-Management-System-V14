import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.admin_ai_keyboard import admin_ai_keyboard
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.states.admin_states import AdminState
from src.core.config.settings import get_settings
from src.services.ai_activity import activity_tracker
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


def _track_start(kind: str, mode: str, request: str) -> None:
    activity_tracker.start(kind=kind, mode=mode, request=request)
    activity_tracker.step("درخواست از پنل ادمین دریافت شد")


def _track_ok(result: str) -> None:
    activity_tracker.step("پاسخ Agent آماده شد")
    activity_tracker.finish(
        success=True,
        outcome=(result or "")[:1500],
        persist_dir=getattr(agent, "repo", None),
    )


def _track_fail(exc: BaseException) -> None:
    activity_tracker.finish(
        success=False,
        error=str(exc)[:1000],
        persist_dir=getattr(agent, "repo", None),
    )


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
        "• 🌐 جستجوی وب\n"
        "• 👁 مشاهده فعالیت (آیا کار شما انجام شد؟)\n"
        "• 🧩 Skills + 🐞/✨ نوشتن کد + PR\n\n"
        "merge به main فقط با تأیید شما در GitHub.",
        reply_markup=admin_ai_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "ai_activity")
async def ai_activity(callback: CallbackQuery):
    if not _owner(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    try:
        if hasattr(agent, "activity_report"):
            result = await asyncio.to_thread(agent.activity_report)
        else:
            activity_tracker.load_persisted(getattr(agent, "repo", None) or ".")
            result = activity_tracker.report_text()
    except AIAgentError as exc:
        result = f"❌ {exc}"
    for part in _chunk(result):
        await callback.message.answer(part)
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
    req = "Audit the repository for bugs, risks, missing tests and architecture issues."
    _track_start("analyze", "assistant", req)
    try:
        result = await asyncio.to_thread(agent.analyze, mode="assistant")
        _track_ok(result)
    except TypeError:
        try:
            result = await asyncio.to_thread(agent.analyze)
            _track_ok(result)
        except AIAgentError as exc:
            _track_fail(exc)
            result = f"❌ {exc}"
    except AIAgentError as exc:
        _track_fail(exc)
        result = f"❌ {exc}"
    for part in _chunk(f"🔎 AI Audit\n\n{result}"):
        await callback.message.answer(part)
    await callback.message.answer(
        "👁 برای دیدن مراحل اجرا: دکمه «فعالیت Agent»",
        reply_markup=admin_ai_keyboard(),
    )


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
        "هر زمان بخواهید ببینید Agent چه کرد: «👁 فعالیت Agent»\n\n"
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
        "لاگ یا توضیح باگ را بفرستید.\n"
        "وضعیت اجرا: «👁 فعالیت Agent»\n\n"
        "خروج: /cancel",
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
        "بگویید کدام منو/پیام بهتر شود.\n"
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
        "موضوع را بفرستید.\n"
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
            "1) Likely root cause\n2) Exact file paths\n3) Concrete fix steps\n4) What to test\n"
            "Do NOT modify files. Answer in Persian; keep paths in English.\n\n"
            f"OWNER INPUT:\n{text[:8000]}"
        )
        header = "🛠 نتیجه دیباگ"
    elif mode == "ui":
        prompt = (
            "You are polishing Telegram UX for RahYar Academy.\n"
            "Suggest clearer Persian copy and keyboard improvements. "
            "Do not change business rules. Answer in Persian.\n\n"
            f"OWNER REQUEST:\n{text[:8000]}"
        )
        header = "🎨 پیشنهاد زیباسازی UI"
    elif mode == "research":
        prompt = (
            "Research the topic using web_search when helpful.\n"
            "Cite URLs. Answer in Persian.\n\n"
            f"TOPIC:\n{text[:8000]}"
        )
        header = "🌐 نتیجه تحقیق"
    else:
        prompt = (
            "You are the owner's coding assistant for RahYar.\n"
            "Be practical about files and patterns. Do NOT modify files.\n"
            "Answer in Persian; keep paths in English.\n\n"
            f"OWNER QUESTION:\n{text[:8000]}"
        )
        header = "💬 دستیار کدنویسی"

    await message.answer(
        "⏳ Agent شروع کرد...\n"
        "برای دیدن پیشرفت لحظه‌ای می‌توانید «👁 فعالیت Agent» را بزنید."
    )
    _track_start("analyze", mode, text)
    activity_tracker.step(f"حالت={mode} · ارسال به API")
    try:
        result = await asyncio.to_thread(agent.analyze, prompt, mode=mode)
        _track_ok(result)
    except TypeError:
        try:
            result = await asyncio.to_thread(agent.analyze, prompt)
            _track_ok(result)
        except AIAgentError as exc:
            _track_fail(exc)
            result = f"❌ {exc}"
    except AIAgentError as exc:
        _track_fail(exc)
        result = f"❌ {exc}"

    for part in _chunk(f"{header}\n\n{result}"):
        await message.answer(part)

    await message.answer(
        "می‌توانید سؤال بعدی را بفرستید، /cancel، یا «👁 فعالیت Agent».",
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
        "🐞 مشکل را دقیق توضیح دهید.\n"
        "در حین اجرا از «👁 فعالیت Agent» وضعیت را ببینید."
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
        "✨ Feature را دقیق توضیح دهید.\n"
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
        "🎨 کدام بخش UI باید زیباتر شود؟\n"
        "Agent کد را عوض می‌کند و PR می‌سازد."
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
        "⏳ clone/تغییر/تست/PR\n"
        "👁 وضعیت زنده: دکمه «فعالیت Agent»"
    )
    _track_start("implement", task_type, task)
    activity_tracker.step("شروع implement (write mode)")
    try:
        result = await asyncio.to_thread(agent.implement, task, task_type)
        # Parse light signals from result text
        if "Files:" in result:
            activity_tracker.step("فایل‌ها در خروجی گزارش شد")
        if "PR:" in result or "http" in result:
            activity_tracker.step("خروجی PR/commit دریافت شد")
        if result.startswith("❌") or "Failed" in result or "failed" in result.lower():
            activity_tracker.finish(
                success=False, error=result[:800], persist_dir=getattr(agent, "repo", None)
            )
        else:
            _track_ok(result)
    except AIAgentError as exc:
        _track_fail(exc)
        result = f"❌ {exc}"
    for part in _chunk(result):
        await message.answer(part)
    await message.answer(
        "برای مرور دقیق مراحل: «👁 فعالیت Agent»",
        reply_markup=admin_ai_keyboard(),
    )


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
