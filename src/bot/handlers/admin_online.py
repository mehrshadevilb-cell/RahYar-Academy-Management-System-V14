from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards.attendance_keyboard import attendance_keyboard

from src.services.reservation_service import ReservationService
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.attendance_service import AttendanceService
from src.services.profile_service import ProfileService
from src.services.online_course_service import OnlineCourseService
from src.bot.states.admin_states import AdminState
from src.bot.keyboards.admin_online_keyboard import (
    admin_online_courses_keyboard,
    payment_model_keyboard,
    admin_online_manage_list_keyboard,
    admin_online_course_detail_keyboard,
)
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.database.models.online_enrollment import PaymentModel
from src.database.models.attendance import AttendanceStatus
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.admin_log_service import AdminLogService
from src.core.constants import admin_actions
from src.core.config.settings import get_settings


router = Router()

reservation_service = ReservationService()
online_enrollment_service = OnlineEnrollmentService()
attendance_service = AttendanceService()
profile_service = ProfileService()
online_course_service = OnlineCourseService()
telegram_repository = TelegramRepository()
admin_log_service = AdminLogService()

settings = get_settings()


def _is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


# NOTE: full file continues in follow-up commit if truncated — see fix/reservation-payment-gate-handlers
