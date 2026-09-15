from __future__ import annotations

import asyncio
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from src.bot.keyboards.music_keyboard import after_result_keyboard, output_keyboard
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
    "من جزئیات موسیقایی مثل Key، Scale، BPM، Groove، سازها و ساختار را خودم تحلیل می‌کنم."
)


def _auto_output(prompt: str) -> str:
    p = prompt.casefold()
    midi_words = ("midi", "نت", "نوت", "ملودی midi", "آکورد midi", "mid file")
    audio_words = ("audio", "wav", "mp3", "صوت", "صدا", "آهنگ", "بیت", "beat", "sound")
    if any(x in p for x in midi_words):
        return "midi"
    if any(x in p for x in audio_words):
        return "audio"
    return "audio"


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


@router.callback_query(F.data == "music_variation")
async def music_variation(callback: CallbackQuery, state: FSMContext, db):
    data = await state.get_data()
    prompt = str(data.get("prompt") or "").strip()
    output = str(data.get("output") or "audio")
    variation = int(data.get("variation") or 0) + 1
    if not prompt:
        await callback.answer("اول یک Prompt بساز", show_alert=True)
        return
    await callback.answer("در حال ساخت Variation…")
    await _generate(callback.message, state, db, prompt, output, variation)


@router.message(MusicState.waiting_prompt)
async def music_prompt(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.casefold() in CANCEL_WORDS:
        await state.clear()
        await message.answer("✅ لغو شد.")
        return
    if len(text) < 3:
        await message.answer("یک توضیح کوتاه‌تر از این نمی‌تواند موسیقی خوبی بسازد؛ مثلاً «dark trap melody in F# minor».")
        return
    if len(text) > 3000:
        await message.answer("Prompt خیلی طولانی است. لطفاً حداکثر ۳۰۰۰ کاراکتر بنویس.")
        return
    await state.update_data(prompt=text, variation=0)
    await state.set_state(MusicState.choosing_output)
    await message.answer("🎚 خروجی را انتخاب کن:", reply_markup=output_keyboard())


@router.callback_query(MusicState.choosing_output, F.data.startswith("music_output:"))
async def music_output(callback: CallbackQuery, state: FSMContext, db):
    output = callback.data.split(":", 1)[1]
    data = await state.get_data()
    prompt = str(data.get("prompt") or "").strip()
    if output == "auto":
        output = _auto_output(prompt)
    await callback.answer("در حال تولید…")
    await _generate(callback.message, state, db, prompt, output, 0)


async def _generate(message: Message, state: FSMContext, db, prompt: str, output: str, variation: int) -> None:
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
                audio, meta = await asyncio.to_thread(generator.generate_audio, prompt, variation)
                ext = (generator.settings.MUSIC_AUDIO_FORMAT or "wav").lower().lstrip(".")
                await message.answer_document(
                    BufferedInputFile(audio, filename=f"rahyar_generated.{ext}"),
                    caption="🔊 <b>RahYar AI Audio</b>\n\nفایل تولیدشده مستقیماً از Music/Audio provider ارسال شده و در Bot ذخیره نمی‌شود.",
                    parse_mode="HTML",
                )
            except MusicAIGeneratorError:
                # If the requested native audio provider is unavailable, produce
                # a real editable MIDI fallback rather than returning nothing.
                midi, plan = await asyncio.to_thread(generator.generate_midi, prompt, variation)
                title = re.sub(r"[^\w\-]+", "_", str(plan.get("title") or "rahyar_music"))[:60]
                await message.answer_document(
                    BufferedInputFile(midi, filename=f"{title}.mid"),
                    caption=(
                        "⚠️ Audio provider فعلاً در دسترس نبود؛ برای اینکه درخواستت بدون خروجی نماند، "
                        "نسخه MIDI حرفه‌ای و قابل ویرایش ساخته شد."
                    ),
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

    await state.update_data(prompt=prompt, output=output, variation=variation)
    await state.set_state(MusicState.choosing_output)
    await message.answer("✅ آماده شد. می‌توانی Variation بگیری یا Prompt جدید بدهی.", reply_markup=after_result_keyboard())
