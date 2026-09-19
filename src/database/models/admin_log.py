from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base
from src.core.utils.time import utcnow


class AdminLog(Base):
    """
    Append-only audit trail of admin actions (product/price changes,
    payment approvals/rejections, license/attendance/installment
    changes, discount code management, etc). Never edited or deleted -
    only ever inserted - so the owner always has an accurate history of
    what happened and who (which admin) did it.

    `admin_telegram_id` is stored as a string (matching
    `TelegramAccount.telegram_id`) since Telegram user ids can exceed
    the range of a 32-bit database integer on some backends.
    """

    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    admin_telegram_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    description: Mapped[str] = mapped_column(String(500), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, index=True
    )
