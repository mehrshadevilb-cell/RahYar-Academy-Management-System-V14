from sqlalchemy.orm import Session

from src.database.models.telegram_channel import TelegramChannel


class TelegramChannelRepository:

    def get_by_id(self, db: Session, record_id: int):
        return (
            db.query(TelegramChannel)
            .filter(TelegramChannel.id == record_id)
            .first()
        )

    def get_by_product(self, db: Session, product_id: int):
        return (
            db.query(TelegramChannel)
            .filter(TelegramChannel.product_id == product_id)
            .order_by(TelegramChannel.sort_order, TelegramChannel.id)
            .all()
        )

    def create(self, db: Session, record: TelegramChannel):
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def delete(self, db: Session, record: TelegramChannel):
        db.delete(record)
        db.commit()
