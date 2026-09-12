from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.models.user import User
from src.database.models.payment import Payment


class StatsService:
    """Simple owner-facing dashboard numbers."""

    def get_summary(self, db: Session) -> dict:

        total_users = db.query(func.count(User.id)).scalar() or 0

        pending_count = (
            db.query(func.count(Payment.id))
            .filter(Payment.status == "pending")
            .scalar()
            or 0
        )

        approved_count = (
            db.query(func.count(Payment.id))
            .filter(Payment.status == "approved")
            .scalar()
            or 0
        )

        total_revenue = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.status == "approved")
            .scalar()
            or 0
        )

        return {
            "total_users": total_users,
            "pending_count": pending_count,
            "approved_count": approved_count,
            "total_revenue": total_revenue,
        }
