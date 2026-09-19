from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.database.models.support_request import SupportRequest, SupportStatus


class SupportRepository:

    def create(self, db: Session, request: SupportRequest) -> SupportRequest:
        db.add(request)
        db.commit()
        db.refresh(request)
        return request

    def get_by_id(self, db: Session, request_id: int) -> SupportRequest | None:
        return db.query(SupportRequest).filter(SupportRequest.id == request_id).first()

    def get_open(self, db: Session, limit: int = 30) -> list[SupportRequest]:
        return (
            db.query(SupportRequest)
            .filter(SupportRequest.status == SupportStatus.OPEN)
            .order_by(SupportRequest.id.asc())
            .limit(limit)
            .all()
        )

    def get_by_user(self, db: Session, user_id: int, limit: int = 10) -> list[SupportRequest]:
        return (
            db.query(SupportRequest)
            .filter(SupportRequest.user_id == user_id)
            .order_by(SupportRequest.id.desc())
            .limit(limit)
            .all()
        )

    def count_open_for_user(self, db: Session, user_id: int) -> int:
        return (
            db.query(SupportRequest)
            .filter(
                SupportRequest.user_id == user_id,
                SupportRequest.status == SupportStatus.OPEN,
            )
            .count()
        )

    def reply(self, db: Session, request: SupportRequest, reply_text: str) -> SupportRequest:
        request.admin_reply = reply_text
        request.status = SupportStatus.ANSWERED
        request.answered_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(request)
        return request

    def close(self, db: Session, request: SupportRequest) -> SupportRequest:
        request.status = SupportStatus.CLOSED
        request.closed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(request)
        return request
