from aiogram.fsm.state import State, StatesGroup


class MusicState(StatesGroup):
    waiting_key = State()
    waiting_progression = State()
    choosing_instrument = State()
