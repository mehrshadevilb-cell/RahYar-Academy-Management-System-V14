from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.core.config.settings import get_settings
from src.database.base import Base

# Import every model so Base.metadata is fully populated before Alembic
# compares it against the database - mirrors src/database/init_db.py,
# which must be kept in sync with this list.
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

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL comes from the app's own Settings (.env), not from
# alembic.ini, so there is exactly one place that owns the connection
# string.
config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade head --sql`)."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection - the normal path."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
