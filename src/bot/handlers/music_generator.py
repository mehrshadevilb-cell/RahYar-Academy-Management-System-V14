from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.bot.states.music_states import MusicState
from src.services.music_generator_service import MusicGeneratorError, MusicGeneratorService

router = Router()
generator = MusicGeneratorService()

MENU_BUTTON_TEXT = "🎼 ساخت ریف/آکورد"
CANCEL_WORDS = {"/cancel", "انصراف"}


def _instrument_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎸 ریف گیتار نایلون", callback_data="music_guitar")],
            [InlineKeyboardButton(text="🎹 آکورد پیانو (ساده)", callback_data="music_piano_close")],
            [InlineKeyboardButton(text="🎹 آکورد پیانو (جاز)", callback_data="music_piano_jazz")],
        ]
    )


@router.message(F.text == MENU_BUTTON_TEXT)
async def music_start(message: Message, state: FSMContext):
    await state.set_state(MusicState.waiting_key)
    await message.answer(
        "🎼 ساخت ریف/آکورد (خروجی MIDI)\n\n"
        "این یک فایل MIDI واقعی (نُت دقیق) می‌سازد، نه فایل صوتی - "
        "در هر DAW یا اپ پخش MIDI قابل استفاده است.\n\n"
        "۱) کلید را بفرستید (مثلاً Am یا C یا F#m).\n"
        "برای انصراف «انصراف» را بفرستید."
    )


@router.message(MusicState.waiting_key)
async def music_key(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text in CANCEL_WORDS:
        await state.clear()
        await message.answer("✅ لغو شد.")
        return
    await state.update_data(key=text)
    await state.set_state(MusicState.waiting_progression)
    await message.answer(
        "۲) پیشرفت آکوردی را با نشانه رومی بفرستید (مثلاً: i - iv - v - iv).\n"
        "هر آکورد معادل یک میزان (bar) در نظر گرفته می‌شود."
    )


@router.message(MusicState.waiting_progression)
async def music_progression(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text in CANCEL_WORDS:
        await state.clear()
        await message.answer("✅ لغو شد.")
        return
    await state.update_data(progression=text)
    await state.set_state(MusicState.choosing_instrument)
    await message.answer("۳) ساز/نوع خروجی را انتخاب کنید:", reply_markup=_instrument_keyboard())


@router.callback_query(MusicState.choosing_instrument, F.data.startswith("music_"))
async def music_generate(callback: CallbackQuery, state: FSMContext):
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
        await callback.message.answer(f"❌ {exc}\n\nبرای شروع دوباره: «{MENU_BUTTON_TEXT}»")
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
    await callback.answer()
