from src.database.base import Base
from src.database.session import engine

# Import all models so SQLAlchemy registers them on Base.metadata.
# Keep in sync with alembic/env.py.
from src.database.models.user import User  # noqa: F401
from src.database.models.telegram_account import TelegramAccount  # noqa: F401
from src.database.models.course import Course  # noqa: F401
from src.database.models.student_profile import StudentProfile  # noqa: F401
from src.database.models.enrollment import Enrollment  # noqa: F401
from src.database.models.payment import Payment  # noqa: F401
from src.database.models.payment_card import PaymentCard  # noqa: F401
from src.database.models.spotplayer_course import SpotPlayerCourse  # noqa: F401
from src.database.models.telegram_channel import TelegramChannel  # noqa: F401
from src.database.models.license import License  # noqa: F401
from src.database.models.invite_link import TelegramInviteLink  # noqa: F401
from src.database.models.online_course import OnlineCourse  # noqa: F401
from src.database.models.online_enrollment import OnlineEnrollment  # noqa: F401
from src.database.models.reservation import Reservation  # noqa: F401
from src.database.models.attendance import Attendance  # noqa: F401
from src.database.models.installment import Installment  # noqa: F401
from src.database.models.discount_code import DiscountCode  # noqa: F401
from src.database.models.admin_log import AdminLog  # noqa: F401
from src.database.models.referral import Referral  # noqa: F401
from src.database.models.support_request import SupportRequest  # noqa: F401
from src.database.models.assignment import Assignment, AssignmentSubmission  # noqa: F401


def init_database():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully")
