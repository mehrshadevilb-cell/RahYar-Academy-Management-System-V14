"""Smoke tests for owner dashboard formatting (no live DB required)."""
from src.services.owner_dashboard_service import (
    InactiveEnrollmentRow,
    OwnerDashboardService,
    OwnerDashboardSummary,
)
from src.services.system_health_service import SystemHealthReport


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
        inactive_online_enrollments=2,
        total_students=40,
    )
    text = summary.format_persian()
    assert "گزارش امروز" in text
    assert "1405-06-25" in text
    assert "1,500,000" in text
    assert "پرداخت محصول: 2" in text
    assert "بدون رزرو اخیر" in text


def test_format_inactive_list_empty():
    text = OwnerDashboardService().format_inactive_list([], days=14)
    assert "پیدا نشد" in text


def test_format_inactive_list_rows():
    rows = [
        InactiveEnrollmentRow(
            enrollment_id=1,
            student_name="علی",
            course_name="پیانو",
            remaining_sessions=3,
            days_since_activity=20,
        )
    ]
    text = OwnerDashboardService().format_inactive_list(rows, days=14)
    assert "علی" in text
    assert "پیانو" in text


def test_system_health_format():
    report = SystemHealthReport(
        build_id="test-build",
        database_ok=True,
        database_error=None,
        reservation_columns_ok=True,
        missing_columns=(),
        dialect="postgresql",
    )
    text = report.format_persian()
    assert "test-build" in text
    assert "اتصال دیتابیس" in text
