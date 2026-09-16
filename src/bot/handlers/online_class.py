import re

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.bot.states.reservation_states import ReservationState
from src.bot.keyboards.reservation_review_keyboard import reservation_review_keyboard
from src.bot.keyboards.jalali_calendar_keyboard import jalali_calendar_keyboard
from src.bot.keyboards.admin_online_keyboard import online_purchase_review_keyboard

from src.services.online_course_service import OnlineCourseService
from src.services.online_enrollment_service import OnlineEnrollmentService
from src.services.reservation_service import ReservationService
from src.services.profile_service import ProfileService
from src.services.online_schedule_service import OnlineScheduleService
from src.services.payment_card_service import PaymentCardService
from src.database.models.online_enrollment import PaymentModel
from src.database.repositories.telegram_repository import TelegramRepository
from src.core.config.settings import get_settings
from src.core.utils.jalali import (
    today_jalali,
    format_jalali_date,
    is_past_jalali_date,
    JALALI_MONTH_NAMES,
)


router = Router()

online_course_service = OnlineCourseService()
online_enrollment_service = OnlineEnrollmentService()
reservation_service = ReservationService()
schedule_service = OnlineScheduleService()
payment_card_service = PaymentCardService()
profile_service = ProfileService()
telegram_repository = TelegramRepository()

settings = get_settings()

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _enrollment_keyboard(enrollment_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 درخواست رزرو کلاس",
                    callback_data=f"reserve_{enrollment_id}",
                )
            ]
        ]
    )


def _slot_keyboard(enrollment_id: int, slots):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🕒 {slot.label}", callback_data=f"reserve_slot_{enrollment_id}_{slot.id}")]
        for slot in slots
    ])


def _catalog_keyboard(courses):
    rows = []
    for course in courses:
        price_bits = []
        if course.monthly_price:
            price_bits.append(f"ماهانه {course.monthly_price:,}")
        if course.term_price:
            price_bits.append(f"ترمی {course.term_price:,}")
        price = " · ".join(price_bits) if price_bits else "قیمت توافقی"
        rows.append([
            InlineKeyboardButton(
                text=f"🎼 {course.name} ({price})",
                callback_data=f"oc_pick_{course.id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _plan_keyboard(course_id: int, course):
    rows = []
    if course.monthly_price is not None:
        rows.append([
            InlineKeyboardButton(
                text=f"ماهانه — {course.monthly_price:,} تومان ({course.monthly_sessions} جلسه)",
                callback_data=f"oc_plan_{course_id}_monthly",
            )
        ])
    if course.term_price is not None:
        rows.append([
            InlineKeyboardButton(
                text=f"ترمی — {course.term_price:,} تومان ({course.term_sessions} جلسه)",
                callback_data=f"oc_plan_{course_id}_term",
            )
        ])
    if not rows:
        rows.append([InlineKeyboardButton(text="ماهانه (قیمت توافقی)", callback_data=f"oc_plan_{course_id}_monthly")])
        rows.append([InlineKeyboardButton(text="ترمی (قیمت توافقی)", callback_data=f"oc_plan_{course_id}_term")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="oc_catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "🎼 کلاس آنلاین")
async def online_class_menu(message: Message, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    enrollments = online_enrollment_service.get_active_by_user(db, user.id)
    if enrollments:
        for enrollment in enrollments:
            plan_text = "ماهانه" if enrollment.payment_model.value == "monthly" else "ترمی"
            await message.answer(
                text=(
                    f"🎼 {enrollment.online_course.name}\n\n"
                    f"نوع پرداخت: {plan_text}\n"
                    f"جلسات باقی‌مانده: {enrollment.remaining_sessions}\n"
                    f"جلسات برگزار شده: {enrollment.completed_sessions}"
                ),
                reply_markup=_enrollment_keyboard(enrollment.id),
            )
        await message.answer(
            "برای ثبت‌نام در کلاس جدید، از دکمه زیر استفاده کنید:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ ثبت‌نام کلاس جدید", callback_data="oc_catalog")]
            ]),
        )
        return

    courses = online_course_service.get_active_courses(db)
    if not courses:
        await message.answer(
            "در حال حاضر کلاس آنلاینی فعال نیست.\n"
            "برای اطلاعات بیشتر با پشتیبانی آکادمی در ارتباط باشید."
        )
        return

    await message.answer(
        "🎼 کلاس‌های آنلاین فعال:\n"
        "یک کلاس را انتخاب کنید تا وارد مرحله پرداخت و سپس رزرو زمان شوید.",
        reply_markup=_catalog_keyboard(courses),
    )


@router.callback_query(F.data == "oc_catalog")
async def online_catalog(callback: CallbackQuery, db):
    courses = online_course_service.get_active_courses(db)
    if not courses:
        await callback.answer("کلاسی فعال نیست.", show_alert=True)
        return
    await callback.message.edit_text(
        "🎼 کلاس‌های آنلاین فعال:\nیک کلاس را انتخاب کنید:",
        reply_markup=_catalog_keyboard(courses),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("oc_pick_"))
async def online_pick_course(callback: CallbackQuery, db):
    course_id = int(callback.data.replace("oc_pick_", ""))
    course = online_course_service.get_course_by_id(db, course_id)
    if not course or not course.is_active:
        await callback.answer("این کلاس در دسترس نیست.", show_alert=True)
        return
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not user:
        await callback.answer("ابتدا /start را بزنید.", show_alert=True)
        return
    existing = online_enrollment_service.get_active_for_user_course(db, user.id, course_id)
    if existing:
        await callback.message.edit_text(
            f"شما از قبل در «{course.name}» ثبت‌نام فعال دارید.\n"
            f"جلسات باقی‌مانده: {existing.remaining_sessions}",
            reply_markup=_enrollment_keyboard(existing.id),
        )
        await callback.answer()
        return
    teacher = f"\n👨‍🏫 مدرس: {course.teacher}" if course.teacher else ""
    await callback.message.edit_text(
        f"🎼 {course.name}{teacher}\n"
        f"⏱ مدت هر جلسه: {course.duration_minutes} دقیقه\n\n"
        "نوع پرداخت را انتخاب کنید:",
        reply_markup=_plan_keyboard(course_id, course),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("oc_plan_"))
async def online_pick_plan(callback: CallbackQuery, state: FSMContext, db):
    parts = callback.data.replace("oc_plan_", "").split("_")
    course_id, plan = int(parts[0]), parts[1]
    course = online_course_service.get_course_by_id(db, course_id)
    if not course or not course.is_active:
        await callback.answer("این کلاس در دسترس نیست.", show_alert=True)
        return
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not user:
        await callback.answer("ابتدا /start را بزنید.", show_alert=True)
        return
    if plan == "monthly":
        amount = course.monthly_price or 0
        sessions = course.monthly_sessions
        plan_fa = "ماهانه"
    else:
        amount = course.term_price or 0
        sessions = course.term_sessions
        plan_fa = "ترمی"
    card = payment_card_service.get_active_card(db)
    if not card:
        await callback.answer("در حال حاضر کارت پرداخت تنظیم نشده است.", show_alert=True)
        return
    await state.update_data(
        online_purchase_course_id=course_id,
        online_purchase_plan=plan,
        online_purchase_amount=amount,
    )
    await state.set_state(ReservationState.waiting_online_purchase_receipt)
    amount_text = f"{amount:,} تومان" if amount else "مبلغ توافقی (با پشتیبانی هماهنگ کنید)"
    await callback.message.edit_text(
        f"💳 ثبت‌نام «{course.name}» — پلن {plan_fa}\n"
        f"🎫 تعداد جلسات: {sessions}\n"
        f"💰 مبلغ: {amount_text}\n\n"
        f"شماره کارت:\n{card.card_number}\n"
        f"به نام:\n{card.card_holder}\n\n"
        "پس از واریز، عکس یا فایل رسید را همینجا ارسال کنید."
    )
    await callback.answer()


@router.message(ReservationState.waiting_online_purchase_receipt, F.photo | F.document)
async def online_purchase_receipt(message: Message, state: FSMContext, bot: Bot, db):
    data = await state.get_data()
    course_id = data.get("online_purchase_course_id")
    plan = data.get("online_purchase_plan")
    amount = int(data.get("online_purchase_amount") or 0)
    course = online_course_service.get_course_by_id(db, course_id) if course_id else None
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not course or not user or not plan:
        await message.answer("❌ خطایی رخ داد. از منوی کلاس آنلاین دوباره شروع کنید.")
        await state.clear()
        return
    proof = message.photo[-1].file_id if message.photo else message.document.file_id
    await state.clear()
    plan_fa = "ماهانه" if plan == "monthly" else "ترمی"
    amount_text = f"{amount:,} تومان" if amount else "توافقی"
    caption = (
        f"🧾 درخواست ثبت‌نام کلاس آنلاین\n\n"
        f"👤 {user.full_name}\n"
        f"📱 {user.phone or '—'}\n"
        f"🎼 {course.name}\n"
        f"📦 پلن: {plan_fa}\n"
        f"💳 مبلغ: {amount_text}"
    )
    markup = online_purchase_review_keyboard(user.id, course.id, plan, amount)
    if message.photo:
        await bot.send_photo(chat_id=settings.OWNER_ID, photo=proof, caption=caption, reply_markup=markup)
    else:
        await bot.send_document(chat_id=settings.OWNER_ID, document=proof, caption=caption, reply_markup=markup)
    await message.answer(
        "✅ رسید شما دریافت شد.\n"
        "پس از تایید ادمین، ثبت‌نام انجام می‌شود و می‌توانید زمان کلاس را رزرو کنید."
    )


@router.callback_query(F.data.regexp(r"^reserve_\d+$"))
async def reservation_start(callback: CallbackQuery, state: FSMContext, db):
    enrollment_id = int(callback.data.replace("reserve_", ""))
    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return
    if enrollment.status.value != "active" or enrollment.remaining_sessions <= 0:
        await callback.answer("این کلاس دیگر جلسه قابل رزرو ندارد.", show_alert=True)
        return
    slots = schedule_service.list_active_slots(db, enrollment.online_course_id)
    if slots:
        await state.update_data(enrollment_id=enrollment_id)
        await callback.message.answer(
            "🕒 زمان هفتگی کلاس را انتخاب کنید:",
            reply_markup=_slot_keyboard(enrollment_id, slots),
        )
        await callback.answer()
        return
    await state.update_data(enrollment_id=enrollment_id)
    await state.set_state(ReservationState.waiting_date)
    jy, jm, _ = today_jalali()
    await callback.message.answer(
        "📅 تاریخ مورد نظر را از تقویم زیر انتخاب کنید:",
        reply_markup=jalali_calendar_keyboard(enrollment_id, jy, jm),
    )
    await callback.answer()


@router.callback_query(F.data == "jcal:noop")
async def jalali_calendar_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("reserve_slot_"))
async def reservation_slot_pick(callback: CallbackQuery, state: FSMContext, db):
    _, _, enrollment_raw, slot_raw = callback.data.split("_")
    enrollment_id, slot_id = int(enrollment_raw), int(slot_raw)
    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return
    slots = schedule_service.list_active_slots(db, enrollment.online_course_id)
    if not any(slot.id == slot_id for slot in slots):
        await callback.answer("این زمان دیگر فعال نیست.", show_alert=True)
        return
    await state.update_data(enrollment_id=enrollment_id, slot_id=slot_id)
    await state.set_state(ReservationState.waiting_date)
    jy, jm, _ = today_jalali()
    await callback.message.answer(
        "📅 تاریخ شروع رزرو را انتخاب کنید:",
        reply_markup=jalali_calendar_keyboard(enrollment_id, jy, jm),
    )
    await callback.answer()


@router.callback_query(ReservationState.waiting_date, F.data.startswith("jcal:nav:"))
async def jalali_calendar_navigate(callback: CallbackQuery, db):
    _, _, enrollment_id_raw, jy_raw, jm_raw = callback.data.split(":")
    enrollment_id, jy, jm = int(enrollment_id_raw), int(jy_raw), int(jm_raw)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return
    await callback.message.edit_reply_markup(reply_markup=jalali_calendar_keyboard(enrollment_id, jy, jm))
    await callback.answer()


@router.callback_query(ReservationState.waiting_date, F.data.startswith("jcal:pick:"))
async def jalali_calendar_pick(callback: CallbackQuery, state: FSMContext, db):
    _, _, enrollment_id_raw, jy_raw, jm_raw, jd_raw = callback.data.split(":")
    enrollment_id, jy, jm, jd = int(enrollment_id_raw), int(jy_raw), int(jm_raw), int(jd_raw)
    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))
    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    if not enrollment or not user or enrollment.user_id != user.id:
        await callback.answer("⛔️ این کلاس متعلق به شما نیست.", show_alert=True)
        return
    if is_past_jalali_date(jy, jm, jd):
        await callback.answer("❌ این تاریخ گذشته است.", show_alert=True)
        return
    requested_date = format_jalali_date(jy, jm, jd)
    data = await state.get_data()
    slot_id = data.get("slot_id")
    if slot_id:
        count = enrollment.online_course.term_sessions if enrollment.payment_model == PaymentModel.TERM else enrollment.online_course.monthly_sessions
        try:
            reservations = schedule_service.create_jalali_reservation_plan(
                db, enrollment, int(slot_id), jy, jm, jd, min(count, enrollment.remaining_sessions)
            )
        except ValueError as exc:
            await state.clear()
            await callback.answer(str(exc), show_alert=True)
            return
        card = payment_card_service.get_active_card(db)
        await state.update_data(reservation_ids=[item.id for item in reservations])
        await state.set_state(ReservationState.waiting_receipt)
        plan_name = "ترمی" if enrollment.payment_model == PaymentModel.TERM else "ماهانه"
        card_text = f"\nشماره کارت: {card.card_number}\nبه نام: {card.card_holder}\n" if card else "\nفعلاً کارت پرداخت تنظیم نشده؛ با پشتیبانی تماس بگیرید.\n"
        await callback.message.edit_text(
            f"✅ برنامه {plan_name} برای {len(reservations)} جلسه ساخته شد.\n"
            f"از تاریخ {requested_date}، زمان انتخابی برای شما رزرو شده است.\n"
            f"برای نهایی شدن، رسید پرداخت را ارسال کنید.{card_text}"
        )
        await callback.answer()
        return
    await state.update_data(requested_date=requested_date)
    await state.set_state(ReservationState.waiting_time)
    await callback.message.edit_text(
        f"📅 تاریخ انتخابی: {jd} {JALALI_MONTH_NAMES[jm - 1]} {jy}\n\n"
        "⏰ ساعت مورد نظر را به فرمت 18:30 ارسال کنید:"
    )
    await callback.answer()


@router.message(ReservationState.waiting_date)
async def reservation_date_typed_fallback(message: Message):
    await message.answer("لطفاً یک تاریخ را از تقویم بالا با ضربه زدن روی عدد روز انتخاب کنید.")


@router.message(ReservationState.waiting_time)
async def reservation_get_time(message: Message, state: FSMContext, bot: Bot, db):
    text = (message.text or "").strip()
    if not TIME_PATTERN.match(text):
        await message.answer("❌ فرمت درست نیست. دوباره بفرستید (مثال: 18:30):")
        return
    data = await state.get_data()
    enrollment_id = data.get("enrollment_id")
    requested_date = data.get("requested_date")
    enrollment = online_enrollment_service.get_by_id(db, enrollment_id)
    if not enrollment:
        await message.answer("❌ خطایی رخ داد.")
        await state.clear()
        return
    reservation = reservation_service.request_reservation(
        db=db, enrollment_id=enrollment_id, requested_date=requested_date, requested_time=text,
    )
    if reservation is None:
        await state.clear()
        await message.answer("⚠️ این زمان را قبلاً درخواست کرده‌اید و هنوز باز است.")
        return
    await state.clear()
    student = profile_service.get_profile_by_id(db, enrollment.user_id)
    await message.answer("✅ درخواست رزرو شما ثبت شد و پس از تایید ادمین به شما اطلاع داده می‌شود.")
    await bot.send_message(
        chat_id=settings.OWNER_ID,
        text=(
            f"📅 درخواست رزرو جدید\n\n"
            f"🎼 کلاس: {enrollment.online_course.name}\n"
            f"👤 هنرجو: {student.full_name if student else enrollment.user_id}\n"
            f"📆 تاریخ: {requested_date}\n"
            f"⏰ ساعت: {text}"
        ),
        reply_markup=reservation_review_keyboard(reservation.id),
    )


@router.message(ReservationState.waiting_receipt)
async def reservation_plan_receipt(message: Message, state: FSMContext, bot: Bot, db):
    proof = None
    if message.photo:
        proof = message.photo[-1].file_id
    elif message.document:
        proof = message.document.file_id
    if not proof:
        await message.answer("لطفاً عکس یا فایل رسید پرداخت را ارسال کنید.")
        return
    data = await state.get_data()
    reservation_ids = data.get("reservation_ids", [])
    submitted = []
    for reservation_id in reservation_ids:
        reservation = reservation_service.submit_payment(db, int(reservation_id), proof)
        if reservation:
            submitted.append(reservation.id)
    await state.clear()
    await message.answer(
        f"✅ رسید برای برنامه {len(submitted)} جلسه ثبت شد. پس از بررسی ادمین، رزروها نهایی می‌شوند."
    )
    if submitted:
        await bot.send_message(
            chat_id=settings.OWNER_ID,
            text=f"💳 رسید پرداخت برنامه آنلاین دریافت شد. رزروهای نیازمند بررسی: {', '.join(map(str, submitted))}",
            reply_markup=reservation_review_keyboard(submitted[0]),
        )
