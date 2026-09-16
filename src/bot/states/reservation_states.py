from aiogram.fsm.state import State, StatesGroup


class ReservationState(StatesGroup):
    waiting_date = State()
    waiting_time = State()
    waiting_receipt = State()
    # Self-service online course purchase
    waiting_online_purchase_receipt = State()
