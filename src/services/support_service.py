from sqlalchemy.orm import Session

from src.database.models.support_request import SupportRequest, SupportStatus
from src.database.repositories.support_repository import SupportRepository

MAX_MESSAGE_LENGTH = 2000
MAX_OPEN_PER_USER = 3


class SupportServiceError(ValueError):
    pass


class SupportService:

    def __init__(self) -> None:
        self.repository = SupportRepository()

    def create_request(
        self,
        db: Session,
        *,
        user_id: int,
        telegram_id: str,
        message: str,
    ) -> SupportRequest:
        text = (message or "").strip()
        if not text:
            raise SupportServiceError("empty_message")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise SupportServiceError("message_too_long")

        open_count = self.repository.count_open_for_user(db, user_id)
        if open_count >= MAX_OPEN_PER_USER:
            raise SupportServiceError("too_many_open")

        return self.repository.create(
            db,
            SupportRequest(
                user_id=user_id,
                telegram_id=str(telegram_id),
                message=text,
                status=SupportStatus.OPEN,
            ),
        )

    def get_open(self, db: Session, limit: int = 30) -> list[SupportRequest]:
        return self.repository.get_open(db, limit)

    def get_by_id(self, db: Session, request_id: int) -> SupportRequest | None:
        return self.repository.get_by_id(db, request_id)

    def get_by_user(self, db: Session, user_id: int, limit: int = 10) -> list[SupportRequest]:
        return self.repository.get_by_user(db, user_id, limit)

    def reply(self, db: Session, request_id: int, reply_text: str) -> SupportRequest:
        request = self.repository.get_by_id(db, request_id)
        if not request:
            raise SupportServiceError("not_found")
        if request.status == SupportStatus.CLOSED:
            raise SupportServiceError("already_closed")

        text = (reply_text or "").strip()
        if not text:
            raise SupportServiceError("empty_reply")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise SupportServiceError("reply_too_long")

        return self.repository.reply(db, request, text)

    def close(self, db: Session, request_id: int) -> SupportRequest:
        request = self.repository.get_by_id(db, request_id)
        if not request:
            raise SupportServiceError("not_found")
        if request.status == SupportStatus.CLOSED:
            raise SupportServiceError("already_closed")
        return self.repository.close(db, request)
