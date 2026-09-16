from aiogram.fsm.state import State, StatesGroup


class AdminState(StatesGroup):
    waiting_new_price = State()
    waiting_product_photo = State()
    waiting_new_card_number = State()
    waiting_new_card_holder = State()
    waiting_student_phone = State()

    waiting_spotplayer_course_id = State()
    waiting_spotplayer_course_name = State()
    waiting_channel_name = State()
    waiting_channel_chat_id = State()

    waiting_online_course_name = State()
    waiting_online_course_teacher = State()
    waiting_online_course_duration = State()
    waiting_online_course_monthly_price = State()
    waiting_online_course_term_price = State()
    waiting_online_course_monthly_sessions = State()
    waiting_online_course_term_sessions = State()
    waiting_online_course_field_edit = State()
    waiting_online_slot = State()

    waiting_enrollment_sessions = State()
    waiting_enrollment_fee = State()
    waiting_enrollment_note = State()
    waiting_class_chat = State()

    waiting_discount_code_text = State()
    waiting_discount_code_type = State()
    waiting_discount_code_value = State()
    waiting_discount_code_max_uses = State()
    waiting_discount_code_expiry = State()

    waiting_log_search_keyword = State()

    waiting_broadcast_content = State()
    waiting_broadcast_confirm = State()

    waiting_ai_task = State()
    waiting_ai_consult = State()
