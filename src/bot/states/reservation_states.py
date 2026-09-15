from aiogram.fsm.state import State, StatesGroup


class ReservationState(StatesGroup):

    waiting_date = State()
    waiting_time = State()
    waiting_payment_proof = State()
