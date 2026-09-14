"""Aggregate a student's academic and payment progress for Telegram display."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from src.database.models.installment import Installment, InstallmentStatus
from src.database.models.license import License
from src.database.models.online_enrollment import OnlineEnrollment
from src.database.models.course import Course


@dataclass
class ProgressSnapshot:
    online_enrollments: list[OnlineEnrollment]
    licenses: list[License]
    installments: list[Installment]
    products_by_id: dict[int, Course]


class ProgressService:

    def get_snapshot(self, db: Session, user_id: int) -> ProgressSnapshot:
        enrollments = (
            db.query(OnlineEnrollment)
            .options(joinedload(OnlineEnrollment.online_course))
            .filter(OnlineEnrollment.user_id == user_id)
            .order_by(OnlineEnrollment.id.desc())
            .all()
        )

        licenses = (
            db.query(License)
            .filter(License.user_id == user_id)
            .order_by(License.id.desc())
            .all()
        )

        enrollment_ids = [e.id for e in enrollments]
        installments: list[Installment] = []
        if enrollment_ids:
            installments = (
                db.query(Installment)
                .filter(Installment.enrollment_id.in_(enrollment_ids))
                .order_by(Installment.due_date.desc())
                .all()
            )

        product_ids = {lic.product_id for lic in licenses}
        products_by_id: dict[int, Course] = {}
        if product_ids:
            products = db.query(Course).filter(Course.id.in_(product_ids)).all()
            products_by_id = {p.id: p for p in products}

        return ProgressSnapshot(
            online_enrollments=enrollments,
            licenses=licenses,
            installments=installments,
            products_by_id=products_by_id,
        )

    def format_persian(self, snapshot: ProgressSnapshot) -> str:
        lines: list[str] = ["📈 پیشرفت شما در آکادمی راه‌یار\n"]

        lines.append("🎼 کلاس‌های آنلاین")
        if not snapshot.online_enrollments:
            lines.append("• هنوز ثبت‌نامی ندارید.\n")
        else:
            status_map = {
                "active": "فعال",
                "paused": "متوقف",
                "ended": "پایان‌یافته",
            }
            for e in snapshot.online_enrollments:
                name = e.online_course.name if e.online_course else f"#{e.online_course_id}"
                st = status_map.get(e.status.value, e.status.value)
                plan = "ماهانه" if e.payment_model.value == "monthly" else "ترمی"
                total_done = e.completed_sessions
                remaining = e.remaining_sessions
                lines.append(
                    f"• {name} ({plan}) — {st}\n"
                    f"  جلسات برگزار شده: {total_done} | باقی‌مانده: {remaining}"
                )
            lines.append("")

        lines.append("🎓 دوره‌های دیجیتال (لایسنس)")
        if not snapshot.licenses:
            lines.append("• لایسنس فعالی ثبت نشده.\n")
        else:
            status_fa = {
                "active": "✅ فعال",
                "failed": "❌ ناموفق",
                "pending": "⏳ در انتظار",
                "expired": "⌛ منقضی",
            }
            for lic in snapshot.licenses:
                product = snapshot.products_by_id.get(lic.product_id)
                title = product.title if product else f"محصول #{lic.product_id}"
                st = status_fa.get(lic.status, lic.status)
                lines.append(f"• {title} — {st}")
            lines.append("")

        lines.append("💰 اقساط")
        if not snapshot.installments:
            lines.append("• قسط بازی ندارید.")
        else:
            inst_status = {
                InstallmentStatus.PENDING: "⏳ در انتظار",
                InstallmentStatus.PAID: "✅ پرداخت‌شده",
                InstallmentStatus.OVERDUE: "⚠️ معوق",
            }
            for inst in snapshot.installments[:8]:
                st = inst_status.get(inst.status, str(inst.status))
                lines.append(
                    f"• قسط {inst.installment_number}: {inst.amount:,} تومان — {st}\n"
                    f"  سررسید: {inst.due_date}"
                )
            if len(snapshot.installments) > 8:
                lines.append(f"• … و {len(snapshot.installments) - 8} مورد دیگر")

        return "\n".join(lines)
