from sqlalchemy.orm import Session

from src.database.models.admin_log import AdminLog


class AdminLogRepository:

    def create(self, db: Session, log: AdminLog) -> AdminLog:
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    def get_recent(self, db: Session, limit: int = 20) -> list[AdminLog]:
        return (
            db.query(AdminLog)
            .order_by(AdminLog.id.desc())
            .limit(limit)
            .all()
        )

    def search(self, db: Session, keyword: str, limit: int = 20) -> list[AdminLog]:
        pattern = f"%{keyword}%"

        return (
            db.query(AdminLog)
            .filter(
                (AdminLog.description.ilike(pattern))
                | (AdminLog.action.ilike(pattern))
            )
            .order_by(AdminLog.id.desc())
            .limit(limit)
            .all()
        )
