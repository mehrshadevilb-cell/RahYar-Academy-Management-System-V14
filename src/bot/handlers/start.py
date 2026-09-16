from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
import unicodedata

from src.bot.keyboards.main_menu import get_main_menu
from src.core.config.settings import get_settings
from src.database.repositories.course_repository import CourseRepository
from src.services.online_course_service import OnlineCourseService
from src.services.referral_service import ReferralService
from src.services.telegram_service import TelegramService
from src.services.profile_service import ProfileService
from src.services.legacy_import_service import LegacyImportService
from src.bot.states.start_states import StartState
from src.bot.states.payment_states import PaymentState
from src.database.models.payment import Payment

router = Router()

telegram_service = TelegramService()
referral_service = ReferralService()
course_repository = CourseRepository()
online_course_service = OnlineCourseService()
profile_service = ProfileService()
legacy_import_service = LegacyImportService()

PHONE_REQUEST_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 ارسال شماره موبایل", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

REFERRAL_PAYLOAD_PREFIX = "ref_"
BUY_PAYLOAD_PREFIX = "buy_"
CLASS_PAYLOAD_PREFIX = "class_"
WEB_PAYMENT_PAYLOAD_PREFIX = "webpay_"


def normalize_iranian_mobile(value: str | None) -> str | None:
    """Return Iranian mobile numbers in the canonical ``09xxxxxxxxx`` form."""
    if not value:
        return None

    digits = "".join(
        str(unicodedata.digit(ch))
        for ch in str(value)
        if unicodedata.category(ch) == "Nd"
    )

    if digits.startswith("0098"):
        digits = "0" + digits[4:]
    elif digits.startswith("98"):
        digits = "0" + digits[2:]
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits

    if len(digits) != 11 or not digits.startswith("09"):
        return None
    return digits


async def _resume_web_payment(message: Message, state: FSMContext, db, user, payment_id: int) -> bool:
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id, Payment.user_id == user.id, Payment.status == "pending")
        .first()
    )
    if not payment:
        await message.answer("❌ سفارش وب پیدا نشد یا قبلاً بررسی شده است.")
        return False
    course = course_repository.get_by_id(db, payment.course_id)
    if not course:
        await message.answer("❌ دورهٔ سفارش پیدا نشد.")
        return False
    await state.update_data(
        course_id=course.id,
        web_payment_id=payment.id,
        final_amount=payment.amount,
        discount_code_id=None,
        discount_amount=0,
    )
    await state.set_state(PaymentState.waiting_receipt)
    await message.answer(
        f"🧾 سفارش وب #{payment.id}\n\n"
        f"🎵 دوره: {course.title}\n"
        f"💳 مبلغ: {payment.amount:,} تومان\n\n"
        "حالا عکس یا فایل رسید کارت‌به‌کارت را همینجا بفرستید تا به همان سفارش وصل شود."
    )
    return True


async def _notify_new_member_start(message: Message, *, is_new: bool, full_name: str, username: str | None) -> None:
    """Notify the configured owner/admin chat without ever breaking /start."""
    settings = get_settings()
    target_chat_id = settings.new_member_notification_chat_id
    if not target_chat_id or not message.from_user:
        return
    # Do not send the notification back to the student if the configured target
    # happens to be the same chat where /start was sent.
    if message.chat.id == target_chat_id:
        return

    status = "🆕 عضو جدید" if is_new else "🔁 ورود مجدد"
    username_text = f"@{username}" if username else "ندارد"
    text = (
        f"🔔 <b>{status}</b>\n\n"
        f"👤 نام: {full_name or '—'}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n"
        f"🔗 Username: {username_text}\n"
        f"💬 Chat ID: <code>{message.chat.id}</code>\n"
        f"📌 نوع کاربر: {'جدید' if is_new else 'عضو قبلی'}"
    )
    try:
        await message.bot.send_message(target_chat_id, text)
    except Exception:
        # Notification failure must never prevent the student from using /start.
        return


@router.message(Command("start"))
async def start_handler(
    message: Message,
    command: CommandObject,
    db,
    state: FSMContext,
):

    user, is_new = telegram_service.get_or_create_user(
        db=db,
        telegram_id=str(message.from_user.id),
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )

    args = (command.args or "").strip()
    web_payment_id = None
    if args.startswith(WEB_PAYMENT_PAYLOAD_PREFIX):
        raw_payment_id = args[len(WEB_PAYMENT_PAYLOAD_PREFIX):]
        if raw_payment_id.isdigit():
            web_payment_id = int(raw_payment_id)
            await state.update_data(pending_web_payment_id=web_payment_id)

    if is_new and args.startswith(REFERRAL_PAYLOAD_PREFIX):
        referrer_telegram_id = args[len(REFERRAL_PAYLOAD_PREFIX):]
        referral_service.create_referral_if_eligible(
            db=db,
            referrer_telegram_id=referrer_telegram_id,
            referred_user_id=user.id,
        )

    await _notify_new_member_start(
        message,
        is_new=is_new,
        full_name=user.full_name,
        username=message.from_user.username,
    )

    await message.answer(
        f"سلام {user.full_name} 👋\n"
        "به آکادمی راه‌یار خوش آمدید.\n"
        f"شماره هنرجویی شما: <code>RH{user.id:06d}</code>",
        reply_markup=PHONE_REQUEST_KEYBOARD if not user.phone else get_main_menu(user.role),
        parse_mode="HTML",
    )

    if not user.phone:
        await state.set_state(StartState.waiting_phone)
        await message.answer(
            "برای ثبت‌نام و رزرو کلاس آنلاین، لطفاً شماره موبایل خود را با دکمه زیر ارسال کنید.",
            reply_markup=PHONE_REQUEST_KEYBOARD,
        )
        return

    if web_payment_id:
        await _resume_web_payment(message, state, db, user, web_payment_id)
        return

    # Deep links from the public website (same catalog / same bot).
    if args.startswith(BUY_PAYLOAD_PREFIX):
        raw_id = args[len(BUY_PAYLOAD_PREFIX):]
        if raw_id.isdigit():
            product = course_repository.get_by_id(db, int(raw_id))
            if product and product.is_active:
                await message.answer(
                    f"🛒 ادامه خرید از وب‌سایت\n\n"
                    f"محصول: {product.title}\n"
                    f"قیمت: {product.price:,} تومان\n\n"
                    "از منوی «📚 دوره ها» محصول را انتخاب کنید و رسید کارت‌به‌کارت را بفرستید.\n"
                    "تا قبل از تأیید مالک، دسترسی فعال نمی‌شود."
                )
                return

    if args.startswith(CLASS_PAYLOAD_PREFIX):
        raw_id = args[len(CLASS_PAYLOAD_PREFIX):]
        if raw_id.isdigit():
            course = online_course_service.get_course_by_id(db, int(raw_id))
            if course and course.is_active:
                await message.answer(
                    f"🎼 کلاس آنلاین از وب‌سایت\n\n"
                    f"کلاس: {course.name}\n"
                    f"مدرس: {course.teacher or '—'}\n\n"
                    "از منوی «🎼 کلاس آنلاین» می‌توانید وضعیت ثبت‌نام و رزرو را ببینید.\n"
                    "ثبت‌نام نهایی توسط آکادمی انجام می‌شود."
                )


@router.message(StartState.waiting_phone, lambda message: message.contact is not None)
async def start_get_phone(message: Message, state: FSMContext, db):
    contact = message.contact
    if not contact or contact.user_id not in (None, message.from_user.id):
        await message.answer("❌ لطفاً شماره خودتان را با دکمه ارسال کنید.")
        return
    phone = normalize_iranian_mobile(contact.phone_number)
    if not phone:
        await message.answer("❌ شماره موبایل معتبر نیست. دوباره تلاش کنید.")
        return
    account = telegram_service.repository.get_by_telegram_id(db, str(message.from_user.id))
    user = account.user if account else None
    if not user:
        await state.clear()
        await message.answer("❌ پروفایل پیدا نشد. لطفاً دوباره /start را بزنید.")
        return
    existing = profile_service.get_profile_by_phone(db, phone)
    if existing and existing.id != user.id:
        if existing.telegram_account is None:
            legacy_import_service.merge_into_live_user(db, existing, user)
        else:
            await message.answer("❌ این شماره قبلاً برای حساب دیگری ثبت شده است.")
            return
    profile_service.update_contact_info(db=db, user=user, full_name=user.full_name, phone=phone)
    data = await state.get_data()
    pending_web_payment_id = data.get("pending_web_payment_id")
    await state.clear()
    await message.answer("✅ شماره شما با موفقیت ثبت شد.", reply_markup=get_main_menu(user.role))
    if pending_web_payment_id:
        await _resume_web_payment(message, state, db, user, int(pending_web_payment_id))
