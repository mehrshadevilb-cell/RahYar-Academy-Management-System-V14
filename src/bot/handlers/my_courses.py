from aiogram import Router
from aiogram.types import Message

from src.database.models.license import License
from src.services.enrollment_service import EnrollmentService
from src.services.profile_service import ProfileService

router = Router()
enrollment_service = EnrollmentService()
profile_service = ProfileService()

_STATUS_LABEL = {
    "active": "🟢 فعال",
    "pending": "🟡 در انتظار صدور",
    "failed": "🔴 ناموفق",
}


def _license_line(db, user_id: int, course_id: int) -> str:
    license_row = (
        db.query(License)
        .filter(License.user_id == user_id, License.product_id == course_id)
        .order_by(License.id.desc())
        .first()
    )
    if not license_row:
        return "🔑 لایسنس: ثبت نشده (اگر تازه خریده‌اید کمی صبر کنید)"
    label = _STATUS_LABEL.get(license_row.status, f"⚪ {license_row.status}")
    parts = [f"🔑 لایسنس: {label}"]
    if license_row.status == "active" and license_row.license_key:
        key = license_row.license_key.strip()
        preview = key if len(key) <= 24 else f"{key[:12]}…{key[-8:]}"
        parts.append(f"کد: <code>{preview}</code>")
    if license_row.status == "failed" and license_row.error_message:
        parts.append(f"توضیح: {license_row.error_message[:120]}")
    if license_row.license_url and license_row.status == "active":
        parts.append(f"لینک: {license_row.license_url}")
    return "\n".join(parts)


@router.message(lambda message: message.text == "🎓 دوره های من")
async def my_courses_handler(message: Message, db):
    telegram_id = str(message.from_user.id)
    user = profile_service.get_profile(db=db, telegram_id=telegram_id)
    if not user:
        await message.answer("❌ کاربر پیدا نشد. لطفاً /start را بزنید.")
        return

    courses = enrollment_service.get_user_courses(db=db, user_id=user.id)
    if not courses:
        await message.answer(
            "📚 هنوز هیچ دوره‌ای خریداری نکرده‌اید.\n"
            "از منوی «📚 دوره ها» می‌توانید خرید را شروع کنید.\n"
            "اگر قبلاً از SpotPlayer خریده بودید و شماره موبایل‌تان یکی است، بعد از ثبت‌نام در ربات دوره‌ها ظاهر می‌شوند."
        )
        return

    blocks = ["🎓 <b>دوره‌های شما</b>\n"]
    for course in courses:
        desc = (course.description or "").strip()
        if len(desc) > 120:
            desc = desc[:117] + "…"
        block = f"🎵 <b>{course.title}</b>\n"
        if desc:
            block += f"📝 {desc}\n"
        block += _license_line(db, user.id, course.id)
        blocks.append(block)

    blocks.append("\n🆘 مشکل لایسنس؟ از «پشتیبانی» پیام بگذارید.")
    text = "\n\n────────\n\n".join(blocks)
    await message.answer(text, parse_mode="HTML")
