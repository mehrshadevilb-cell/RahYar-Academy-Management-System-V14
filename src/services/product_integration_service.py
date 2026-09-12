from sqlalchemy.orm import Session

from src.database.models.spotplayer_course import SpotPlayerCourse
from src.database.models.telegram_channel import TelegramChannel
from src.database.repositories.spotplayer_course_repository import (
    SpotPlayerCourseRepository,
)
from src.database.repositories.telegram_channel_repository import (
    TelegramChannelRepository,
)


class ProductIntegrationService:
    """
    Manages the delivery-specific configuration attached to a `Course`
    (product): SpotPlayer course ids for SPOTPLAYER-delivery products, and
    Telegram channels for TELEGRAM/ArtistYar-delivery products.

    This intentionally stays a thin CRUD layer - `LicenseService` and
    `ArtistYarService` already own the actual delivery logic and read
    these records (via `product.spotplayer_courses` / `.telegram_channels`)
    at delivery time, so nothing here duplicates that behavior.
    """

    def __init__(self):
        self.spotplayer_repository = SpotPlayerCourseRepository()
        self.channel_repository = TelegramChannelRepository()

    # ---------------- SpotPlayer ----------------

    def get_spotplayer_courses(self, db: Session, product_id: int):
        return self.spotplayer_repository.get_by_product(db, product_id)

    def add_spotplayer_course(
        self, db: Session, product_id: int, spotplayer_course_id: str, course_name: str | None
    ) -> SpotPlayerCourse:
        return self.spotplayer_repository.create(
            db,
            SpotPlayerCourse(
                product_id=product_id,
                spotplayer_course_id=spotplayer_course_id,
                course_name=course_name,
            ),
        )

    def toggle_spotplayer_course(self, db: Session, record_id: int):
        record = self.spotplayer_repository.get_by_id(db, record_id)
        if not record:
            return None
        record.enabled = not record.enabled
        db.commit()
        db.refresh(record)
        return record

    def remove_spotplayer_course(self, db: Session, record_id: int) -> bool:
        record = self.spotplayer_repository.get_by_id(db, record_id)
        if not record:
            return False
        self.spotplayer_repository.delete(db, record)
        return True

    # ---------------- ArtistYar channels ----------------

    def get_channels(self, db: Session, product_id: int):
        return self.channel_repository.get_by_product(db, product_id)

    def add_channel(
        self, db: Session, product_id: int, name: str, chat_id: str
    ) -> TelegramChannel:
        return self.channel_repository.create(
            db,
            TelegramChannel(product_id=product_id, name=name, chat_id=chat_id),
        )

    def toggle_channel(self, db: Session, record_id: int):
        record = self.channel_repository.get_by_id(db, record_id)
        if not record:
            return None
        record.enabled = not record.enabled
        db.commit()
        db.refresh(record)
        return record

    def remove_channel(self, db: Session, record_id: int) -> bool:
        record = self.channel_repository.get_by_id(db, record_id)
        if not record:
            return False
        self.channel_repository.delete(db, record)
        return True
