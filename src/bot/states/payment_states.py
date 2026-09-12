from aiogram.fsm.state import State, StatesGroup


class PaymentState(StatesGroup):

    waiting_receipt = State()

    waiting_discount_code = State()
