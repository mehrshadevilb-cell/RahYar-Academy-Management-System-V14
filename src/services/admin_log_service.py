from sqlalchemy.orm import Session

from src.database.models.admin_log import AdminLog
from src.database.repositories.admin_log_repository import AdminLogRepository


class AdminLogService:
    """
    Thin logging facade used by every admin-facing handler. Writing a log
    entry is fire-and-forget from the caller's point of view: it never
    raises and never blocks the actual admin action on a logging failure
    (the record is committed right away, independent of whatever else
    the calling handler does next).
    """

    def __init__(self):
        self.repository = AdminLogRepository()

    def log(
        self,
        db: Session,
        admin_telegram_id: int | str,
        action: str,
        description: str,
    ) -> AdminLog:
        return self.repository.create(
            db,
            AdminLog(
                admin_telegram_id=str(admin_telegram_id),
                action=action,
                description=description,
            ),
        )

    def get_recent(self, db: Session, limit: int = 20) -> list[AdminLog]:
        return self.repository.get_recent(db, limit)

    def search(self, db: Session, keyword: str, limit: int = 20) -> list[AdminLog]:
        return self.repository.search(db, keyword, limit)
