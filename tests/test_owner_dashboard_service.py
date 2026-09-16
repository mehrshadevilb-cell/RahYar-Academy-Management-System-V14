"""Smoke tests for owner dashboard formatting (no live DB required)."""
from src.services.owner_dashboard_service import OwnerDashboardSummary


def test_format_persian_includes_key_sections():
    summary = OwnerDashboardSummary(
        jalali_today="1405-06-25",
        pending_payments=2,
        pending_reservations=1,
        classes_today=3,
        installments_due_today=1,
        installments_overdue=0,
        revenue_today=1_500_000,
        revenue_week=4_000_000,
        revenue_month=12_000_000,
        active_online_enrollments=8,
        total_students=40,
    )
    text = summary.format_persian()
    assert "گزارش امروز" in text
    assert "1405-06-25" in text
    assert "1,500,000" in text
    assert "پرداخت محصول: 2" in text
    assert "رزرو کلاس: 1" in text
