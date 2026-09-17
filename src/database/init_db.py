import os

from src.database.base import Base
from src.database.session import engine

# Import all models so SQLAlchemy registers them on Base.metadata.
from src.database.models.user import User  # noqa: F401
from src.database.models.telegram_account import TelegramAccount  # noqa: F401
from src.database.models.course import Course  # noqa: F401
from src.database.models.free_lesson import FreeLesson  # noqa: F401
from src.database.models.student_profile import StudentProfile  # noqa: F401
from src.database.models.enrollment import Enrollment  # noqa: F401
from src.database.models.payment import Payment  # noqa: F401
from src.database.models.payment_card import PaymentCard  # noqa: F401
from src.database.models.spotplayer_course import SpotPlayerCourse  # noqa: F401
from src.database.models.telegram_channel import TelegramChannel  # noqa: F401
from src.database.models.license import License  # noqa: F401
from src.database.models.invite_link import TelegramInviteLink  # noqa: F401
from src.database.models.online_course import OnlineCourse  # noqa: F401
from src.database.models.online_time_slot import OnlineTimeSlot  # noqa: F401
from src.database.models.online_enrollment import OnlineEnrollment  # noqa: F401
from src.database.models.reservation import Reservation  # noqa: F401
from src.database.models.attendance import Attendance  # noqa: F401
from src.database.models.installment import Installment  # noqa: F401
from src.database.models.discount_code import DiscountCode  # noqa: F401
from src.database.models.admin_log import AdminLog  # noqa: F401
from src.database.models.referral import Referral  # noqa: F401
from src.database.models.support_request import SupportRequest  # noqa: F401
from src.database.models.site_event import SiteEvent  # noqa: F401
from src.database.models.assignment import Assignment, AssignmentSubmission  # noqa: F401
from src.database.models.class_inquiry import ClassInquiry  # noqa: F401
from src.database.models.knowledge import KnowledgeItem, QuizQuestion  # noqa: F401
from src.database.models.ai_provider import AIProvider  # noqa: F401
from src.database.models.ai_model import AIModel  # noqa: F401


def init_database():
    """Dev/test helper only. Production schema is owned by Alembic."""
    env = (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()
    if env in {"production", "prod", "staging"}:
        raise RuntimeError("init_database() is blocked in production/staging. Use: alembic upgrade head")
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully")
