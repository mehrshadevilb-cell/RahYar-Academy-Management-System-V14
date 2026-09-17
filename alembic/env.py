from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from src.core.config.settings import get_settings
from src.database.base import Base

# Import every model so Base.metadata is fully populated before Alembic
# compares it against the database - mirrors src/database/init_db.py.
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
from src.database.models.online_enrollment import OnlineEnrollment  # noqa: F401
from src.database.models.reservation import Reservation  # noqa: F401
from src.database.models.attendance import Attendance  # noqa: F401
from src.database.models.installment import Installment  # noqa: F401
from src.database.models.discount_code import DiscountCode  # noqa: F401
from src.database.models.admin_log import AdminLog  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)
target_metadata = Base.metadata

# PostgreSQL advisory locks are connection-scoped. A fixed application-specific
# lock key prevents two Render instances from running Alembic concurrently.
POSTGRES_MIGRATION_LOCK_ID = 782145903


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        is_postgres = connection.dialect.name == "postgresql"
        lock_acquired = False
        try:
            if is_postgres:
                connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": POSTGRES_MIGRATION_LOCK_ID})
                lock_acquired = True

            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if is_postgres and lock_acquired:
                connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": POSTGRES_MIGRATION_LOCK_ID})


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
