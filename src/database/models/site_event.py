from datetime import datetime

from sqlalchemy import DateTime, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base
from src.core.utils.time import utcnow


class SiteEvent(Base):
    __tablename__ = "site_events"
    __table_args__ = (
        Index("ix_site_events_type_created", "event_type", "created_at"),
        Index("ix_site_events_path_created", "path", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(240), nullable=False, default="/")
    visitor_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
