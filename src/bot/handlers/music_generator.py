from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from src.bot.keyboards.music_keyboard import (
    after_result_keyboard,
    instrument_keyboard,
    key_keyboard,
    progression_keyboard,
)
from src.bot.states.music_states import MusicState
from src.services.music_generator_service import MusicGeneratorError, MusicGeneratorService

router = Router()
generator = MusicGeneratorService()

MENU_BUTTON_TEXT = "🎼 ساخت ریف/آکورد"
CANCEL_WORDS = {"/cancel", "انصراف"}

INTRO_TEXT = (
    "🎼 ساخت ریف/آکورد (خروجی MIDI)\n\n"
    "این یک فایل MIDI واقعی (نُت دقیق) می‌سازد، نه فایل صوتی - "
    "در هر DAW یا اپ پخش MIDI قابل استفاده است.\n\n"
    "۱) یک کلید را انتخاب کن یا خودت تایپ کن:"
)


async def _clear_and_answer(callback: CallbackQuery, state: FSMContext, text: str) -> None:
    await state.clear()
    await callback.message.answer(text)
    await callback.answer()


# ---------------------------------------------------------------------------
# Entry point + global cancel/restart (no state filter: reachable from any
# step of the flow so the person is never stuck mid-way through).
# ---------------------------------------------------------------------------


@router.message(F.text == MENU_BUTTON_TEXT)
async def music_start(message: Message, state: FSMContext):
    await state.set_state(MusicState.waiting_key)
    await message.answer(INTRO_TEXT, reply_markup=key_keyboard())


@router.callback_query(F.data == "music_cancel")
async def music_cancel(callback: CallbackQuery, state: FSMContext):
    await _clear_and_answer(callback, state, "✅ لغو شد.")


@router.callback_query(F.data == "music_restart")
async def music_restart(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MusicState.waiting_key)
    await callback.message.answer(INTRO_TEXT, reply_markup=key_keyboard())
    await callback.answer()


# ---------------------------------------------------------------------------
# Step 1: key
# ---------------------------------------------------------------------------


@router.callback_query(MusicState.waiting_key, F.data.startswith("musickey:"))
async def music_key_picked(callback: CallbackQuery, state: FSMContext):
    key_text = callback.data.split(":", 1)[1]
    await state.update_data(key=key_text)
    await state.set_state(MusicState.waiting_progression)
    await callback.message.answer(
        f"کلید انتخاب‌شده: {key_text}\n\n"
        "۲) یک پیشرفت آکوردی را انتخاب کن یا خودت تایپ کن:",
        reply_markup=progression_keyboard(),
    )
    await callback.answer()


@router.callback_query(MusicState.waiting_key, F.data == "musickey_custom")
async def music_key_custom_prompt(callback: CallbackQuery):
    await callback.message.answer("کلید را تایپ کن (مثلاً Am یا C یا F#m):")
    await callback.answer()


@router.message(MusicState.waiting_key)
async def music_key_typed(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text in CANCEL_WORDS:
        await state.clear()
        await message.answer("✅ لغو شد.")
        return
    await state.update_data(key=text)
    await state.set_state(MusicState.waiting_progression)
    await message.answer(
        "۲) یک پیشرفت آکوردی را انتخاب کن یا خودت تایپ کن:",
        reply_markup=progression_keyboard(),
    )


# ---------------------------------------------------------------------------
# Step 2: chord progression
# ---------------------------------------------------------------------------


@router.callback_query(MusicState.waiting_progression, F.data.startswith("musicprog:"))
async def music_progression_picked(callback: CallbackQuery, state: FSMContext):
    progression_text = callback.data.split(":", 1)[1]
    await state.update_data(progression=progression_text)
    await state.set_state(MusicState.choosing_instrument)
    await callback.message.answer(
        f"پیشرفت انتخاب‌شده: {progression_text}\n\n"
        "۳) ساز/نوع خروجی را انتخاب کن:",
        reply_markup=instrument_keyboard(),
    )
    await callback.answer()


@router.callback_query(MusicState.waiting_progression, F.data == "musicprog_custom")
async def music_progression_custom_prompt(callback: CallbackQuery):
    await callback.message.answer(
        "پیشرفت آکوردی را با نشانه رومی تایپ کن (مثلاً: i - iv - v - iv).\n"
        "هر آکورد معادل یک میزان (bar) در نظر گرفته می‌شود."
    )
    await callback.answer()


@router.message(MusicState.waiting_progression)
async def music_progression_typed(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text in CANCEL_WORDS:
        await state.clear()
        await message.answer("✅ لغو شد.")
        return
    await state.update_data(progression=text)
    await state.set_state(MusicState.choosing_instrument)
    await message.answer("۳) ساز/نوع خروجی را انتخاب کن:", reply_markup=instrument_keyboard())


# ---------------------------------------------------------------------------
# Step 3: instrument -> generate
# ---------------------------------------------------------------------------


@router.callback_query(MusicState.choosing_instrument, F.data.startswith("music_"))
async def music_generate(callback: CallbackQuery, state: FSMContext):
    if callback.data in ("music_cancel", "music_restart"):
        return  # handled by the dedicated global handlers above

    data = await state.get_data()
    key_text = data.get("key", "")
    progression_text = data.get("progression", "")
    await state.clear()

    if callback.data == "music_guitar":
        instrument, voicing, tempo = "nylon_guitar", "close", 140
        instrument_label = "ریف گیتار نایلون"
    elif callback.data == "music_piano_jazz":
        instrument, voicing, tempo = "piano", "jazz", 100
        instrument_label = "آکورد پیانو (جاز)"
    else:
        instrument, voicing, tempo = "piano", "close", 100
        instrument_label = "آکورد پیانو (ساده)"

    try:
        midi_bytes = generator.generate(
            key_text=key_text,
            progression_text=progression_text,
            instrument=instrument,
            voicing=voicing,
            tempo=tempo,
        )
    except MusicGeneratorError as exc:
        await callback.message.answer(
            f"❌ {exc}\n\nبرای شروع دوباره: «{MENU_BUTTON_TEXT}»",
            reply_markup=after_result_keyboard(),
        )
        await callback.answer()
        return

    safe_key = "".join(ch for ch in key_text if ch.isalnum()) or "key"
    filename = f"rahyar_{safe_key}_{instrument}.mid"
    await callback.message.answer_document(
        BufferedInputFile(midi_bytes, filename=filename),
        caption=(
            f"🎼 کلید: {key_text}\n"
            f"پیشرفت: {progression_text}\n"
            f"خروجی: {instrument_label} | تمپو: {tempo}\n\n"
            "فایل MIDI است (نُت دقیق، نه صدای ضبط‌شده)؛ در هر DAW یا "
            "اپلیکیشن پخش MIDI قابل استفاده است."
        ),
    )
    await callback.message.answer("می‌خوای یکی دیگه بسازی؟", reply_markup=after_result_keyboard())
    await callback.answer()
