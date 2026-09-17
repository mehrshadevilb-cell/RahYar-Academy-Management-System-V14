from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from src.database.models.installment import InstallmentStatus
from src.database.repositories.telegram_repository import TelegramRepository
from src.services.installment_service import InstallmentService
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.profile_service import ProfileService
from src.services.online_course_service import OnlineCourseService
from src.bot.keyboards.admin_installments_keyboard import installment_review_keyboard
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.services.admin_log_service import AdminLogService
from src.core.constants import admin_actions
from src.core.admin_access import is_admin_user


router = Router()

installment_service = InstallmentService()
online_enrollment_service = OnlineEnrollmentService()
profile_service = ProfileService()
online_course_service = OnlineCourseService()
telegram_repository = TelegramRepository()
admin_log_service = AdminLogService()


def _installment_caption(db, installment, label: str) -> str:

    enrollment = online_enrollment_service.get_by_id(db, installment.enrollment_id)
    student = profile_service.get_profile_by_id(db, enrollment.user_id) if enrollment else None
    course = (
        online_course_service.get_course_by_id(db, enrollment.online_course_id)
        if enrollment else None
    )

    return (
        f"{label}\n"
        f"🧾 قسط #{installment.id} (شماره {installment.installment_number})\n"
        f"👤 {student.full_name if student else 'نامشخص'}\n"
        f"🎼 {course.name if course else 'نامشخص'}\n"
        f"💳 مبلغ: {installment.amount:,} تومان\n"
        f"📆 سررسید: {installment.due_date}"
    )


@router.callback_query(F.data == "admin_installments")
async def admin_installments_menu(callback: CallbackQuery, db):

    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    pending = installment_service.get_pending(db)
    overdue = installment_service.get_overdue(db)

    if not pending and not overdue:
        await callback.message.edit_text(
            "✅ هیچ قسط در انتظار یا معوقی وجود ندارد.",
            reply_markup=admin_back_button(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"💰 {len(overdue)} قسط معوق، {len(pending)} قسط در انتظار سررسید:",
        reply_markup=admin_back_button(),
    )

    for installment in overdue:
        text = _installment_caption(db, installment, "⚠️ معوق")
        await callback.message.answer(text, reply_markup=installment_review_keyboard(installment.id))

    for installment in pending:
        text = _installment_caption(db, installment, "⏳ در انتظار سررسید")
        await callback.message.answer(text, reply_markup=installment_review_keyboard(installment.id))

    await callback.answer()


@router.callback_query(F.data.startswith("inst_paid_"))
async def installment_mark_paid(callback: CallbackQuery, bot: Bot, db):

    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    installment_id = int(callback.data.replace("inst_paid_", ""))
    installment = installment_service.get_by_id(db, installment_id)

    if not installment:
        await callback.answer("قسط پیدا نشد", show_alert=True)
        return

    if installment.status == InstallmentStatus.PAID:
        await callback.answer("این قسط قبلاً پرداخت‌شده ثبت شده است.", show_alert=True)
        return

    installment_service.mark_paid(db, installment)

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.INSTALLMENT_MARK_PAID,
        f"قسط شماره {installment.installment_number} (#{installment.id}) "
        f"به مبلغ {installment.amount:,} تومان پرداخت‌شده ثبت شد",
    )

    enrollment = online_enrollment_service.get_by_id(db, installment.enrollment_id)

    if enrollment:
        telegram_account = telegram_repository.get_by_user_id(db, enrollment.user_id)

        if telegram_account:
            await bot.send_message(
                chat_id=telegram_account.telegram_id,
                text=(
                    f"✅ پرداخت قسط شماره {installment.installment_number} "
                    f"شما ثبت و تایید شد."
                ),
            )

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ پرداخت ثبت شد."
    )

    await callback.answer("ثبت شد ✅")
