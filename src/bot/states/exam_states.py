from aiogram.fsm.state import State, StatesGroup


class AdminExamState(StatesGroup):
    waiting_course_id = State()
    waiting_title = State()
    waiting_pass_score = State()
    waiting_max_attempts = State()
    waiting_question_text = State()
    waiting_options = State()
    waiting_correct_index = State()
