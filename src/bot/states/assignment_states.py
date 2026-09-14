from aiogram.fsm.state import State, StatesGroup


class StudentAssignmentState(StatesGroup):
    waiting_submission = State()


class AdminAssignmentState(StatesGroup):
    waiting_course_id = State()
    waiting_title = State()
    waiting_description = State()
    waiting_review_feedback = State()
