from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from src.bot.states.admin_states import AdminState
from src.bot.keyboards.admin_menu_keyboard import admin_main_menu, admin_back_button
from src.bot.keyboards.admin_products_keyboard import (
    admin_products_keyboard,
    admin_product_detail_keyboard,
)
from src.bot.keyboards.admin_cards_keyboard import admin_cards_keyboard
from src.bot.keyboards.payment_review_keyboard import payment_review_keyboard
from src.bot.keyboards.admin_products_keyboard import (
    spotplayer_courses_keyboard,
    telegram_channels_keyboard,
)

from src.services.course_service import CourseService
from src.services.payment_service import PaymentService
from src.services.payment_card_service import PaymentCardService
from src.services.stats_service import StatsService
from src.services.product_integration_service import ProductIntegrationService
from src.services.admin_log_service import AdminLogService
from src.core.constants import admin_actions
from src.core.admin_access import is_admin_user

router = Router()

course_service = CourseService()
payment_service = PaymentService()
payment_card_service = PaymentCardService()
stats_service = StatsService()
product_integration_service = ProductIntegrationService()
admin_log_service = AdminLogService()


@router.message(Command("admin"))
@router.message(F.text == "🛠 پنل مدیریت")
async def admin_home_command(message: Message):
    if not is_admin_user(message.from_user):
        return
    await message.answer("🛠 پنل مدیریت راه‌یار", reply_markup=admin_main_menu())


@router.callback_query(F.data == "admin_home")
async def admin_home_callback(callback: CallbackQuery):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    await callback.message.edit_text("🛠 پنل مدیریت راه‌یار", reply_markup=admin_main_menu())
    await callback.answer()


# ---------------- Products ----------------

@router.callback_query(F.data == "admin_products")
async def admin_products_list(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    courses = course_service.get_all_courses(db)
    await callback.message.edit_text("📚 محصولات:\n(✅ فعال / 🚫 غیرفعال)", reply_markup=admin_products_keyboard(courses))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_product_view_"))
async def admin_product_view(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    course_id = int(callback.data.replace("admin_product_view_", ""))
    course = course_service.get_course_by_id(db, course_id)
    if not course:
        await callback.answer("محصول پیدا نشد", show_alert=True)
        return
    status = "✅ فعال" if course.is_active else "🚫 غیرفعال"
    await callback.message.edit_text(text=f"🎵 {course.title}\n\n💳 قیمت: {course.price:,} تومان\nوضعیت: {status}\n", reply_markup=admin_product_detail_keyboard(course))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_product_toggle_"))
async def admin_product_toggle(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    course_id = int(callback.data.replace("admin_product_toggle_", ""))
    course = course_service.toggle_active(db, course_id)
    if not course:
        await callback.answer("محصول پیدا نشد", show_alert=True)
        return
    status = "✅ فعال" if course.is_active else "🚫 غیرفعال"
    admin_log_service.log(db, callback.from_user.id, admin_actions.PRODUCT_TOGGLE, f"محصول «{course.title}» به وضعیت {status} تغییر کرد")
    await callback.message.edit_text(text=f"🎵 {course.title}\n\n💳 قیمت: {course.price:,} تومان\nوضعیت: {status}\n", reply_markup=admin_product_detail_keyboard(course))
    await callback.answer("وضعیت تغییر کرد ✅")


@router.callback_query(F.data.startswith("admin_product_price_"))
async def admin_product_price_start(callback: CallbackQuery, state: FSMContext, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    course_id = int(callback.data.replace("admin_product_price_", ""))
    course = course_service.get_course_by_id(db, course_id)
    if not course:
        await callback.answer("محصول پیدا نشد", show_alert=True)
        return
    await state.update_data(course_id=course_id)
    await state.set_state(AdminState.waiting_new_price)
    await callback.message.answer(f"قیمت جدید «{course.title}» را به تومان و فقط به‌صورت عدد بفرستید:")
    await callback.answer()


@router.message(AdminState.waiting_new_price)
async def admin_product_price_set(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    raw = (message.text or "").replace(",", "").strip()
    if not raw.isdigit():
        await message.answer("❌ لطفاً فقط عدد بفرستید. مثال: 15000000")
        return
    data = await state.get_data()
    course_id = data.get("course_id")
    old_course = course_service.get_course_by_id(db, course_id)
    old_price = old_course.price if old_course else None
    course = course_service.update_price(db, course_id, int(raw))
    await state.clear()
    if not course:
        await message.answer("❌ محصول پیدا نشد.")
        return
    admin_log_service.log(db, message.from_user.id, admin_actions.PRODUCT_PRICE_CHANGE, f"قیمت «{course.title}» از {old_price:,} به {course.price:,} تومان تغییر کرد" if old_price is not None else f"قیمت «{course.title}» به {course.price:,} تومان تغییر کرد")
    await message.answer(f"✅ قیمت «{course.title}» به {course.price:,} تومان تغییر کرد.", reply_markup=admin_back_button("admin_products"))


@router.callback_query(F.data.startswith("admin_product_photo_"))
async def admin_product_photo_start(callback: CallbackQuery, state: FSMContext, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    course_id = int(callback.data.replace("admin_product_photo_", ""))
    course = course_service.get_course_by_id(db, course_id)
    if not course:
        await callback.answer("محصول پیدا نشد", show_alert=True)
        return
    await state.update_data(course_id=course_id)
    await state.set_state(AdminState.waiting_product_photo)
    await callback.message.answer(f"📷 عکس جدید برای «{course.title}» را ارسال کنید:")
    await callback.answer()


@router.message(AdminState.waiting_product_photo, F.photo)
async def admin_product_photo_set(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    data = await state.get_data()
    course_id = data.get("course_id")
    file_id = message.photo[-1].file_id
    course = course_service.update_thumbnail(db, course_id, file_id)
    await state.clear()
    if not course:
        await message.answer("❌ محصول پیدا نشد.")
        return
    admin_log_service.log(db, message.from_user.id, admin_actions.PRODUCT_PHOTO_CHANGE, f"عکس «{course.title}» تغییر کرد")
    await message.answer_photo(photo=file_id, caption=f"✅ عکس «{course.title}» با موفقیت تغییر کرد.", reply_markup=admin_back_button("admin_products"))


@router.message(AdminState.waiting_product_photo)
async def admin_product_photo_invalid(message: Message):
    if not is_admin_user(message.from_user):
        return
    await message.answer("❌ لطفاً یک عکس ارسال کنید (نه متن یا فایل دیگر).")


# ---------------- Product integrations: SpotPlayer course ids ----------------

@router.callback_query(F.data.startswith("admin_product_spotplayer_"))
async def admin_spotplayer_list(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    product_id = int(callback.data.replace("admin_product_spotplayer_", ""))
    course = course_service.get_course_by_id(db, product_id)
    if not course:
        await callback.answer("محصول پیدا نشد", show_alert=True)
        return
    records = product_integration_service.get_spotplayer_courses(db, product_id)
    text = f"🔌 کدهای دوره SpotPlayer برای «{course.title}»:"
    if not records:
        text += "\n\n⚠️ هنوز هیچ کدی ثبت نشده - بدون این، صدور لایسنس شکست می‌خورد."
    await callback.message.edit_text(text, reply_markup=spotplayer_courses_keyboard(product_id, records))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_sp_toggle_"))
async def admin_spotplayer_toggle(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    record_id = int(callback.data.replace("admin_sp_toggle_", ""))
    record = product_integration_service.toggle_spotplayer_course(db, record_id)
    if not record:
        await callback.answer("رکورد پیدا نشد", show_alert=True)
        return
    admin_log_service.log(db, callback.from_user.id, admin_actions.SPOTPLAYER_COURSE_TOGGLE, f"وضعیت کد SpotPlayer «{record.spotplayer_course_id}» تغییر کرد ({'فعال' if record.enabled else 'غیرفعال'})")
    records = product_integration_service.get_spotplayer_courses(db, record.product_id)
    await callback.message.edit_reply_markup(reply_markup=spotplayer_courses_keyboard(record.product_id, records))
    await callback.answer("وضعیت تغییر کرد ✅")


@router.callback_query(F.data.startswith("admin_sp_add_"))
async def admin_spotplayer_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    product_id = int(callback.data.replace("admin_sp_add_", ""))
    await state.update_data(product_id=product_id)
    await state.set_state(AdminState.waiting_spotplayer_course_id)
    await callback.message.answer("کد دوره (course id) SpotPlayer را بفرستید:")
    await callback.answer()


@router.message(AdminState.waiting_spotplayer_course_id)
async def admin_spotplayer_add_id(message: Message, state: FSMContext):
    if not is_admin_user(message.from_user):
        return
    spotplayer_course_id = (message.text or "").strip()
    if not spotplayer_course_id:
        await message.answer("❌ کد نمی‌تواند خالی باشد. دوباره بفرستید:")
        return
    await state.update_data(spotplayer_course_id=spotplayer_course_id)
    await state.set_state(AdminState.waiting_spotplayer_course_name)
    await message.answer("نام نمایشی این دوره را بفرستید (یا برای رد کردن «-» بفرستید):")


@router.message(AdminState.waiting_spotplayer_course_name)
async def admin_spotplayer_add_name(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    raw_name = (message.text or "").strip()
    course_name = None if raw_name in ("", "-") else raw_name
    data = await state.get_data()
    product_id = data.get("product_id")
    spotplayer_course_id = data.get("spotplayer_course_id")
    await state.clear()
    product_integration_service.add_spotplayer_course(db, product_id, spotplayer_course_id, course_name)
    admin_log_service.log(db, message.from_user.id, admin_actions.SPOTPLAYER_COURSE_ADD, f"کد SpotPlayer «{spotplayer_course_id}» به محصول شماره {product_id} اضافه شد")
    records = product_integration_service.get_spotplayer_courses(db, product_id)
    await message.answer("✅ کد دوره SpotPlayer ثبت شد.", reply_markup=spotplayer_courses_keyboard(product_id, records))


# ---------------- Product integrations: ArtistYar Telegram channels ----------------

@router.callback_query(F.data.startswith("admin_product_channels_"))
async def admin_channels_list(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    product_id = int(callback.data.replace("admin_product_channels_", ""))
    course = course_service.get_course_by_id(db, product_id)
    if not course:
        await callback.answer("محصول پیدا نشد", show_alert=True)
        return
    records = product_integration_service.get_channels(db, product_id)
    text = f"📡 کانال‌های تلگرام برای «{course.title}»:"
    if not records:
        text += "\n\n⚠️ هنوز هیچ کانالی ثبت نشده - بدون این، هیچ لینکی برای هنرجو ساخته نمی‌شود."
    await callback.message.edit_text(text, reply_markup=telegram_channels_keyboard(product_id, records))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ch_toggle_"))
async def admin_channel_toggle(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    record_id = int(callback.data.replace("admin_ch_toggle_", ""))
    record = product_integration_service.toggle_channel(db, record_id)
    if not record:
        await callback.answer("رکورد پیدا نشد", show_alert=True)
        return
    admin_log_service.log(db, callback.from_user.id, admin_actions.CHANNEL_TOGGLE, f"وضعیت کانال «{record.name}» تغییر کرد ({'فعال' if record.enabled else 'غیرفعال'})")
    records = product_integration_service.get_channels(db, record.product_id)
    await callback.message.edit_reply_markup(reply_markup=telegram_channels_keyboard(record.product_id, records))
    await callback.answer("وضعیت تغییر کرد ✅")


@router.callback_query(F.data.startswith("admin_ch_add_"))
async def admin_channel_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    product_id = int(callback.data.replace("admin_ch_add_", ""))
    await state.update_data(product_id=product_id)
    await state.set_state(AdminState.waiting_channel_name)
    await callback.message.answer("نام کانال را بفرستید (مثلاً «فایل‌ها» یا «Record»):")
    await callback.answer()


@router.message(AdminState.waiting_channel_name)
async def admin_channel_add_name(message: Message, state: FSMContext):
    if not is_admin_user(message.from_user):
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ نام نمی‌تواند خالی باشد. دوباره بفرستید:")
        return
    await state.update_data(channel_name=name)
    await state.set_state(AdminState.waiting_channel_chat_id)
    await message.answer("شناسه (chat_id) عددی کانال را بفرستید (ربات باید ادمین کانال با دسترسی ساخت لینک دعوت باشد):")


@router.message(AdminState.waiting_channel_chat_id)
async def admin_channel_add_chat_id(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    chat_id = (message.text or "").strip()
    if not chat_id.lstrip("-").isdigit():
        await message.answer("❌ شناسه کانال باید عددی باشد (مثال: -1001234567890). دوباره بفرستید:")
        return
    data = await state.get_data()
    product_id = data.get("product_id")
    channel_name = data.get("channel_name")
    await state.clear()
    product_integration_service.add_channel(db, product_id, channel_name, chat_id)
    admin_log_service.log(db, message.from_user.id, admin_actions.CHANNEL_ADD, f"کانال «{channel_name}» به محصول شماره {product_id} اضافه شد")
    records = product_integration_service.get_channels(db, product_id)
    await message.answer("✅ کانال ثبت شد.", reply_markup=telegram_channels_keyboard(product_id, records))


# ---------------- Pending payments ----------------

@router.callback_query(F.data == "admin_pending")
async def admin_pending_list(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    pending = payment_service.get_pending(db)
    if not pending:
        await callback.message.edit_text("✅ هیچ پرداخت در انتظاری وجود ندارد.", reply_markup=admin_back_button())
        await callback.answer()
        return
    await callback.message.edit_text(f"💳 {len(pending)} پرداخت در انتظار بررسی:", reply_markup=admin_back_button())
    for payment in pending:
        course = course_service.get_course_by_id(db, payment.course_id)
        caption = f"🧾 شماره پرداخت: {payment.id}\n🎵 دوره: {course.title if course else 'نامشخص'}\n💳 مبلغ: {payment.amount:,} تومان"
        if payment.receipt_file_id:
            await callback.message.answer_photo(photo=payment.receipt_file_id, caption=caption, reply_markup=payment_review_keyboard(payment.id))
        else:
            await callback.message.answer(caption, reply_markup=payment_review_keyboard(payment.id))
    await callback.answer()


# ---------------- Payment cards ----------------

@router.callback_query(F.data == "admin_cards")
async def admin_cards_list(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    active_card = payment_card_service.get_active_card(db)
    if active_card:
        text = f"🏦 کارت فعال فعلی:\n\n{active_card.card_number}\nبه نام {active_card.card_holder}"
    else:
        text = "⚠️ در حال حاضر هیچ کارت فعالی ثبت نشده است."
    await callback.message.edit_text(text, reply_markup=admin_cards_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_card_add")
async def admin_card_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    await state.set_state(AdminState.waiting_new_card_number)
    await callback.message.answer("شماره کارت جدید را بفرستید (فقط عدد، بدون فاصله):")
    await callback.answer()


@router.message(AdminState.waiting_new_card_number)
async def admin_card_add_number(message: Message, state: FSMContext):
    if not is_admin_user(message.from_user):
        return
    card_number = (message.text or "").replace(" ", "").replace("-", "").strip()
    if not card_number.isdigit() or len(card_number) != 16:
        await message.answer("❌ شماره کارت باید ۱۶ رقم و فقط عدد باشد. دوباره بفرستید:")
        return
    await state.update_data(card_number=card_number)
    await state.set_state(AdminState.waiting_new_card_holder)
    await message.answer("نام صاحب کارت را بفرستید:")


@router.message(AdminState.waiting_new_card_holder)
async def admin_card_add_holder(message: Message, state: FSMContext, db):
    if not is_admin_user(message.from_user):
        return
    card_holder = (message.text or "").strip()
    if not card_holder:
        await message.answer("❌ نام نمی‌تواند خالی باشد. دوباره بفرستید:")
        return
    data = await state.get_data()
    card_number = data.get("card_number")
    payment_card_service.add_card(db, card_number, card_holder)
    admin_log_service.log(db, message.from_user.id, admin_actions.PAYMENT_CARD_ADD, f"کارت پرداخت جدید به نام «{card_holder}» ثبت و فعال شد")
    await state.clear()
    await message.answer("✅ کارت جدید ثبت و فعال شد.", reply_markup=admin_back_button())


# ---------------- Stats ----------------

@router.callback_query(F.data == "admin_stats")
async def admin_stats_view(callback: CallbackQuery, db):
    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return
    summary = stats_service.get_summary(db)
    await callback.message.edit_text(text=f"📊 آمار کلی\n\n👥 تعداد کاربران: {summary['total_users']:,}\n✅ پرداخت‌های تایید شده: {summary['approved_count']:,}\n⏳ پرداخت‌های در انتظار: {summary['pending_count']:,}\n💰 مجموع درآمد: {summary['total_revenue']:,} تومان\n", reply_markup=admin_back_button())
    await callback.answer()
