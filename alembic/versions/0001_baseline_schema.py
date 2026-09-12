"""baseline schema - current v9 models

This is the adoption point for Alembic in a project that previously only
used `Base.metadata.create_all()` (see src/database/init_db.py). Rather
than hand-transcribing every column/enum/FK across 18 models - which is
exactly the kind of manual step that silently drifts from the real ORM
models over time - this migration builds the schema straight from
`Base.metadata`, which is already the single source of truth the app
itself uses.

How to adopt this on an existing environment:

- Fresh/empty database: run `alembic upgrade head` - it will create every
  table from scratch, same as `init_database()` does today.
- Existing database that already has these tables (any current dev/staging
  DB created via `init_database()`): do NOT run `upgrade head` directly,
  since the tables already exist. Instead run `alembic stamp head` to tell
  Alembic "this schema is already at this revision" without touching any
  table. From then on, write normal incremental migrations on top of this
  baseline.

Every migration from this point forward must be a real, explicit
upgrade()/downgrade() pair - do not add another metadata-wide migration
after this one.

Revision ID: 0001
Revises:
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op

from src.database.base import Base

# Import every model so Base.metadata is fully populated - keep this list
# identical to alembic/env.py and src/database/init_db.py.
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


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
