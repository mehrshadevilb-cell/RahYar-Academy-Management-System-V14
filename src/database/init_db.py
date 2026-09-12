from src.database.base import Base
from src.database.session import engine

# Import همه مدل‌ها برای اینکه SQLAlchemy آن‌ها را بشناسد
from src.database.models.user import User
from src.database.models.telegram_account import TelegramAccount
from src.database.models.course import Course
from src.database.models.student_profile import StudentProfile
from src.database.models.enrollment import Enrollment
from src.database.models.payment import Payment
from src.database.models.payment_card import PaymentCard
from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.telegram_channel import TelegramChannel
from src.database.models.license import License
from src.database.models.invite_link import TelegramInviteLink
from src.database.models.online_course import OnlineCourse
from src.database.models.online_enrollment import OnlineEnrollment
from src.database.models.reservation import Reservation
from src.database.models.attendance import Attendance
from src.database.models.installment import Installment
from src.database.models.discount_code import DiscountCode
from src.database.models.admin_log import AdminLog
from src.database.models.referral import Referral



def init_database():

    Base.metadata.create_all(
        bind=engine
    )



if __name__ == "__main__":

    init_database()

    print("Database initialized successfully")