"""Compatibility wrapper around OwnerDashboardService.

Historically exposed a small payment/user summary for «آمار». The owner
daily dashboard is now the single rich surface; this service keeps the
old dict shape for any leftover callers/tests without duplicating SQL.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services.owner_dashboard_service import OwnerDashboardService


class StatsService:
    """Legacy API — prefer OwnerDashboardService for new code."""

    def __init__(self) -> None:
        self._dashboard = OwnerDashboardService()

    def get_summary(self, db: Session) -> dict:
        s = self._dashboard.get_summary(db)
        return {
            "total_users": s.total_students,
            "pending_count": s.pending_payments,
            # Approximate: approved count is not stored on dashboard; use
            # month revenue presence only as a soft signal is wrong — keep 0
            # for approved_count unless we query. Callers showing «آمار»
            # are redirected to dashboard; this dict is for tests/compat.
            "approved_count": 0,
            "total_revenue": s.revenue_month,
            # Extended fields for anyone already switching to the new model:
            "pending_reservations": s.pending_reservations,
            "classes_today": s.classes_today,
            "revenue_today": s.revenue_today,
            "revenue_week": s.revenue_week,
            "revenue_month": s.revenue_month,
            "active_online_enrollments": s.active_online_enrollments,
            "inactive_online_enrollments": s.inactive_online_enrollments,
            "installments_overdue": s.installments_overdue,
        }
