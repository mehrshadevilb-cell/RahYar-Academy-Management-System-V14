"""Telegram-group entry point for the RahYar AI Music Generator.

The panel is intentionally opt-in: a group message does not start a
music-generation session unless the member invokes /ai_generator.
Generation quota is still enforced by the music generator service.
"""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.music_keyboard import generator_panel_keyboard, output_keyboard
from src.bot.states.music_states import MusicState

router = Router()


@router.message(Command("ai_generator"))
async def group_ai_generator_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🎵 <b>RahYar AI Music Generator</b>\n\n"
        "از پنل زیر خروجی موردنظر را انتخاب کن.\n"
        "بعد از انتخاب، Prompt را برای من بفرست.",
        parse_mode="HTML",
        reply_markup=generator_panel_keyboard(),
    )


@router.callback_query(F.data.startswith("music_open:"))
async def group_ai_generator_open(callback: CallbackQuery, state: FSMContext):
    requested = callback.data.split(":", 1)[1]
    if requested not in {"audio", "midi", "auto"}:
        await callback.answer("گزینه نامعتبر است.", show_alert=True)
        return

    await state.clear()
    await state.update_data(group_panel=True, requested_output=requested, advanced={}, variation=0)
    await state.set_state(MusicState.waiting_prompt)
    await callback.answer()
    await callback.message.answer(
        "✍️ Prompt را بفرست؛ فارسی یا انگلیسی فرقی ندارد.\n\n"
        "مثال: <i>dark trap beat, F# minor, 140 BPM, heavy 808</i>",
        parse_mode="HTML",
        reply_markup=output_keyboard(),
    )
