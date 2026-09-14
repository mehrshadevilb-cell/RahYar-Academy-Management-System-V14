from aiogram.fsm.state import State, StatesGroup


class SupportState(StatesGroup):
    waiting_message = State()


class AdminSupportState(StatesGroup):
    waiting_reply = State()
