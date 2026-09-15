from aiogram.fsm.state import State, StatesGroup


class StartState(StatesGroup):
    waiting_phone = State()
