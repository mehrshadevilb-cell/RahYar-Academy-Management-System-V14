from aiogram.fsm.state import State, StatesGroup


class MusicState(StatesGroup):
    waiting_prompt = State()
    choosing_output = State()
    advanced = State()
    waiting_edit_prompt = State()
    waiting_extend = State()
    generating = State()
