from aiogram.fsm.state import State, StatesGroup


class MusicState(StatesGroup):
    waiting_prompt = State()
    choosing_output = State()
    generating = State()
