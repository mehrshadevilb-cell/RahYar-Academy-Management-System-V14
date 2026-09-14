from aiogram.fsm.state import State, StatesGroup


class AdminClassSlotState(StatesGroup):
    waiting_course_id = State()
    waiting_date = State()
    waiting_time = State()
