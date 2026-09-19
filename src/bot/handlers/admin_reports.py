from datetime import datetime, timezone

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, BufferedInputFile

from src.bot.keyboards.admin_reports_keyboard import admin_reports_keyboard
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.services.report_service import ReportService
from src.core.config.settings import get_settings


router = Router()

report_service = ReportService()

settings = get_settings()


def _is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID


def _filename(prefix: str) -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"


@router.callback_query(F.data == "admin_reports")
async def admin_reports_menu(callback: CallbackQuery):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await callback.message.edit_text(
        "📊 خروجی CSV کدام گزارش را می‌خواهید؟",
        reply_markup=admin_reports_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "report_payments")
async def admin_report_payments(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await callback.answer("در حال ساخت گزارش...")

    content = report_service.payments_report(db)

    await bot.send_document(
        chat_id=callback.from_user.id,
        document=BufferedInputFile(content, filename=_filename("payments")),
        caption="💳 گزارش پرداخت‌ها",
        reply_markup=admin_back_button("admin_reports"),
    )


@router.callback_query(F.data == "report_students")
async def admin_report_students(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await callback.answer("در حال ساخت گزارش...")

    content = report_service.students_report(db)

    await bot.send_document(
        chat_id=callback.from_user.id,
        document=BufferedInputFile(content, filename=_filename("students")),
        caption="👥 گزارش هنرجویان",
        reply_markup=admin_back_button("admin_reports"),
    )


@router.callback_query(F.data == "report_online_enrollments")
async def admin_report_online_enrollments(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await callback.answer("در حال ساخت گزارش...")

    content = report_service.online_enrollments_report(db)

    await bot.send_document(
        chat_id=callback.from_user.id,
        document=BufferedInputFile(content, filename=_filename("online_enrollments")),
        caption="🎼 گزارش ثبت‌نام کلاس‌های آنلاین",
        reply_markup=admin_back_button("admin_reports"),
    )


@router.callback_query(F.data == "report_installments")
async def admin_report_installments(callback: CallbackQuery, bot: Bot, db):

    if not _is_owner(callback.from_user.id):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await callback.answer("در حال ساخت گزارش...")

    content = report_service.installments_report(db)

    await bot.send_document(
        chat_id=callback.from_user.id,
        document=BufferedInputFile(content, filename=_filename("installments")),
        caption="💰 گزارش اقساط",
        reply_markup=admin_back_button("admin_reports"),
    )
