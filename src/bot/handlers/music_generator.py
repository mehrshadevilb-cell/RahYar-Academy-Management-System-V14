from __future__ import annotations

import asyncio
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from src.bot.keyboards.music_keyboard import advanced_keyboard, after_result_keyboard, output_keyboard
from src.bot.states.music_states import MusicState
from src.services.music_ai_generator_service import MusicAIGeneratorError, MusicAIGeneratorService
from src.services.music_generation_quota import MusicQuota

router = Router()
generator = MusicAIGeneratorService()
quota = MusicQuota()

MENU_BUTTON_TEXT = "🎵 AI Generator"
LEGACY_MENU_BUTTON_TEXT = "🎼 ساخت ریف/آکورد"
CANCEL_WORDS = {"/cancel", "انصراف", "لغو"}

INTRO = (
    "🎵 <b>AI Music Generator</b>\n\n"
    "فقط چیزی که می‌خواهی بسازی را بنویس؛ حتی خیلی ساده.\n\n"
    "مثلاً:\n"
    "• یه ملودی دارک برای رپ، F# minor، حدود 140 BPM\n"
    "• cinematic piano با strings و drums، احساسی و بزرگ\n"
    "• یه trap beat خشن با 808 و hi-hat سریع\n\n"
    "من Key، Scale، BPM، Groove، سازها و ساختار را خودم تحلیل می‌کنم."
)


def _auto_output(prompt: str) -> str:
    """Prefer the connected AI router's MIDI path unless audio was explicit."""
    p = prompt.casefold()
    if any(x in p for x in ("midi", "نت", "نوت", "ملودی midi", "آکورد midi", "mid file")):
        return "midi"
    if any(x in p for x in ("audio", "wav", "mp3", "صوت", "فایل صوتی", "آهنگ صوتی")):
        return "audio"
    # Normal configured AI providers are text/JSON capable, not audio generators.
    return "midi"


def _settings_summary(settings: dict) -> str:
    return (
        f"BPM: {settings.get('bpm') or 'Auto'} | "
        f"Key/Scale: {settings.get('key') or 'Auto'} | "
        f"Length: {settings.get('length') or 'Auto'} | "
        f"Style: {settings.get('style') or 'Auto'}"
    )


def _prompt_with_settings(prompt: str, settings: dict) -> str:
    extra = []
    if settings.get("bpm"):
        extra.append(f"Target BPM: {settings['bpm']}")
    if settings.get("key"):
        extra.append(f"Target key/scale: {settings['key']}")
    if settings.get("length"):
        extra.append(f"Target length: {settings['length']}")
    if settings.get("style"):
        extra.append(f"Style/instruments: {settings['style']}")
    return prompt if not extra else prompt + "\n\n[Advanced production settings]\n" + "\n".join(extra)


async def _start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(MusicState.waiting_prompt)
    await message.answer(INTRO, parse_mode="HTML")


@router.message(F.text.in_({MENU_BUTTON_TEXT, LEGACY_MENU_BUTTON_TEXT}))
async def music_start(message: Message, state: FSMContext):
    await _start(message, state)


@router.message(F.text == "/music")
async def music_command(message: Message, state: FSMContext):
    await _start(message, state)


@router.callback_query(F.data == "music_cancel")
async def music_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("لغو شد")
    await callback.message.answer("✅ لغو شد.")


@router.callback_query(F.data == "music_restart")
async def music_restart(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _start(callback.message, state)


@router.callback_query(F.data == "music_preview")
async def music_preview(callback: CallbackQuery, state: FSMContext):
    await callback.answer("پیش‌نمایش همان فایل ارسالی بالاست؛ Bot فایل را ذخیره نمی‌کند.", show_alert=True)


@router.callback_query(F.data == "music_edit_prompt")
async def music_edit_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(MusicState.waiting_edit_prompt)
    await callback.message.answer("✏️ Prompt جدید/اصلاح‌شده را بفرست:")


@router.message(MusicState.waiting_edit_prompt)
async def music_edit_prompt_message(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.casefold() in CANCEL_WORDS:
        await state.set_state(MusicState.choosing_output)
        await message.answer("لغو شد.", reply_markup=after_result_keyboard())
        return
    if len(text) < 3 or len(text) > 3000:
        await message.answer("Prompt باید بین ۳ تا ۳۰۰۰ کاراکتر باشد.")
        return
    await state.update_data(prompt=text, variation=0, advanced={})
    await state.set_state(MusicState.choosing_output)
    await message.answer("✅ Prompt به‌روزرسانی شد. خروجی را انتخاب کن:", reply_markup=output_keyboard())


@router.callback_query(F.data == "music_extend")
async def music_extend(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(MusicState.waiting_extend)
    await callback.message.answer(
        "➕ بگو ادامه را چطور می‌خواهی؛ مثلاً:\n"
        "«16 bars ادامه بده، با build-up و بعد drop»\n\n"
        "این قابلیت بدون ذخیره فایل، یک نسخه جدید از arrangement می‌سازد."
    )


@router.message(MusicState.waiting_extend)
async def music_extend_message(message: Message, state: FSMContext, db):
    extension = (message.text or "").strip()
    if extension.casefold() in CANCEL_WORDS:
        await state.set_state(MusicState.choosing_output)
        await message.answer("لغو شد.", reply_markup=after_result_keyboard())
        return
    if len(extension) < 3 or len(extension) > 1000:
        await message.answer("توضیح Extend باید بین ۳ تا ۱۰۰۰ کاراکتر باشد.")
        return
    data = await state.get_data()
    prompt = str(data.get("prompt") or "").strip()
    output = str(data.get("output") or _auto_output(prompt))
    settings = dict(data.get("advanced") or {})
    extended_prompt = _prompt_with_settings(f"{prompt}\n\nExtend the arrangement: {extension}", settings)
    await _generate(message, state, db, extended_prompt, output, int(data.get("variation") or 0) + 1, allow_fallback=False)


@router.callback_query(F.data == "music_variation")
async def music_variation(callback: CallbackQuery, state: FSMContext, db):
    data = await state.get_data()
    prompt = str(data.get("prompt") or "").strip()
    output = str(data.get("output") or "midi")
    settings = dict(data.get("advanced") or {})
    variation = int(data.get("variation") or 0) + 1
    if not prompt:
        await callback.answer("اول یک Prompt بساز", show_alert=True)
        return
    await callback.answer("در حال ساخت Variation…")
    await _generate(callback.message, state, db, _prompt_with_settings(prompt, settings), output, variation)


@router.callback_query(F.data == "music_advanced")
async def music_advanced(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(MusicState.advanced)
    data = await state.get_data()
    settings = dict(data.get("advanced") or {})
    await callback.message.answer(
        "⚙️ <b>Advanced Music Settings</b>\n\n"
        f"{_settings_summary(settings)}\n\n"
        "هر مورد را جداگانه تنظیم کن؛ Auto یعنی تصمیم با AI.",
        parse_mode="HTML",
        reply_markup=advanced_keyboard(),
    )


@router.callback_query(MusicState.advanced, F.data.startswith("music_adv:"))
async def music_advanced_action(callback: CallbackQuery, state: FSMContext, db):
    action = callback.data.split(":", 1)[1]
    if action == "back":
        await callback.answer()
        await state.set_state(MusicState.choosing_output)
        await callback.message.answer("🎚 انتخاب خروجی:", reply_markup=output_keyboard())
        return
    if action == "reset":
        await state.update_data(advanced={})
        await callback.answer("تنظیمات ریست شد")
        await callback.message.edit_text("⚙️ تنظیمات Advanced ریست شد.\n\nهمه موارد روی Auto هستند.", reply_markup=advanced_keyboard())
        return
    if action == "generate":
        data = await state.get_data()
        prompt = str(data.get("prompt") or "").strip()
        if not prompt:
            await callback.answer("Prompt موجود نیست", show_alert=True)
            return
        output = str(data.get("output") or _auto_output(prompt))
        settings = dict(data.get("advanced") or {})
        await callback.answer("در حال تولید…")
        await _generate(callback.message, state, db, _prompt_with_settings(prompt, settings), output, int(data.get("variation") or 0))
        return
    prompts = {
        "bpm": "🎚 BPM را وارد کن (مثلاً 140) یا Auto بنویس:",
        "key": "🎼 Key / Scale را وارد کن (مثلاً F# minor) یا Auto بنویس:",
        "length": "⏱ مدت/تعداد میزان را وارد کن (مثلاً 60s یا 32 bars) یا Auto بنویس:",
        "style": "🎹 سبک و سازها را وارد کن (مثلاً dark trap, 808, piano, strings) یا Auto بنویس:",
    }
    if action in prompts:
        await state.update_data(advanced_field=action)
        await callback.answer()
        await callback.message.answer(prompts[action])


@router.message(MusicState.advanced)
async def music_advanced_message(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    data = await state.get_data()
    field = data.get("advanced_field")
    if not field:
        await message.answer("از دکمه‌های Advanced استفاده کن.", reply_markup=advanced_keyboard())
        return
    settings = dict(data.get("advanced") or {})
    if value.casefold() in {"auto", "اتومات", "خودکار"}:
        settings.pop(field, None)
    else:
        if field == "bpm":
            match = re.fullmatch(r"\d{2,3}", value)
            if not match or not 40 <= int(value) <= 220:
                await message.answer("BPM باید عددی بین 40 تا 220 باشد.")
                return
        settings[field] = value
    await state.update_data(advanced=settings, advanced_field=None)
    await message.answer(f"✅ ذخیره شد.\n\n{_settings_summary(settings)}", reply_markup=advanced_keyboard())


@router.message(MusicState.waiting_prompt)
async def music_prompt(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.casefold() in CANCEL_WORDS:
        await state.clear()
        await message.answer("✅ لغو شد.")
        return
    if len(text) < 3:
        await message.answer("مثلاً «dark trap melody in F# minor» بنویس.")
        return
    if len(text) > 3000:
        await message.answer("Prompt خیلی طولانی است. حداکثر ۳۰۰۰ کاراکتر.")
        return
    await state.update_data(prompt=text, variation=0, advanced={})
    await state.set_state(MusicState.choosing_output)
    await message.answer("🎚 خروجی را انتخاب کن:", reply_markup=output_keyboard())


@router.callback_query(MusicState.choosing_output, F.data.startswith("music_output:"))
async def music_output(callback: CallbackQuery, state: FSMContext, db):
    requested = callback.data.split(":", 1)[1]
    data = await state.get_data()
    prompt = str(data.get("prompt") or "").strip()
    output = _auto_output(prompt) if requested == "auto" else requested
    allow_fallback = requested == "auto"
    settings = dict(data.get("advanced") or {})
    await callback.answer("در حال تولید…")
    await _generate(callback.message, state, db, _prompt_with_settings(prompt, settings), output, 0, allow_fallback=allow_fallback)


async def _generate(
    message: Message,
    state: FSMContext,
    db,
    prompt: str,
    output: str,
    variation: int,
    *,
    allow_fallback: bool = False,
) -> None:
    user_id = message.from_user.id
    is_student = quota.is_rah_yar_student(db, user_id)
    allowed, limit, remaining = quota.reserve(user_id, is_student)
    if not allowed:
        label = "دانشجوی راه‌یار" if is_student else "کاربر عمومی"
        await message.answer(f"⛔ سهمیه امروزت تمام شده است.\n\nگروه: {label}\nسقف روزانه: {limit} generation")
        return

    await state.set_state(MusicState.generating)
    status = await message.answer(
        f"🎛 در حال ساخت…\n\nPrompt: {prompt[:600]}\n\n"
        f"سهمیه باقی‌مانده بعد از این درخواست: {remaining}"
    )
    try:
        if output == "midi":
            midi, plan = await asyncio.to_thread(generator.generate_midi, prompt, variation)
            title = re.sub(r"[^\w\-]+", "_", str(plan.get("title") or "rahyar_music"))[:60]
            await message.answer_document(
                BufferedInputFile(midi, filename=f"{title}.mid"),
                caption=(
                    "🎹 <b>RahYar AI MIDI</b>\n"
                    f"BPM: {plan.get('bpm', '—')} | Key: {plan.get('key', '—')} | Scale: {plan.get('scale', '—')}\n"
                    f"Tracks: {len(plan.get('tracks', []))} | Bars: {plan.get('bars', '—')}"
                ),
                parse_mode="HTML",
            )
        else:
            try:
                audio, _meta = await asyncio.to_thread(generator.generate_audio, prompt, variation)
                ext = (generator.settings.MUSIC_AUDIO_FORMAT or "wav").lower().lstrip(".")
                await message.answer_document(
                    BufferedInputFile(audio, filename=f"rahyar_generated.{ext}"),
                    caption="🔊 <b>RahYar AI Audio</b>\n\nفایل مستقیم برای کار داخل DAW؛ Bot فایل را ذخیره نمی‌کند.",
                    parse_mode="HTML",
                )
            except MusicAIGeneratorError:
                if not allow_fallback:
                    raise
                midi, plan = await asyncio.to_thread(generator.generate_midi, prompt, variation)
                title = re.sub(r"[^\w\-]+", "_", str(plan.get("title") or "rahyar_music"))[:60]
                await message.answer_document(
                    BufferedInputFile(midi, filename=f"{title}.mid"),
                    caption="⚠️ Audio provider در دسترس نبود؛ نسخه MIDI قابل‌ویرایش ساخته شد.",
                )
    except MusicAIGeneratorError as exc:
        quota.release(user_id)
        await message.answer(f"❌ {exc}")
        await state.clear()
        return
    except Exception:
        quota.release(user_id)
        await message.answer("❌ تولید ناموفق بود. سهمیه این تلاش برایت برگردانده شد؛ دوباره امتحان کن.")
        await state.clear()
        return
    finally:
        try:
            await status.delete()
        except Exception:
            pass

    original_prompt = prompt.split("\n\n[Advanced production settings]", 1)[0].strip()
    await state.update_data(prompt=original_prompt, output=output, variation=variation)
    await state.set_state(MusicState.choosing_output)
    await message.answer("✅ آماده شد. می‌توانی Preview، Variation، Extend، Edit Prompt یا Advanced را استفاده کنی.", reply_markup=after_result_keyboard())
