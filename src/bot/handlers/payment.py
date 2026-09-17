import re

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.states.payment_states import PaymentState
from src.bot.states.registration import RegistrationState
from src.bot.keyboards.payment_review_keyboard import payment_review_keyboard
from src.bot.keyboards.license_retry_keyboard import license_retry_keyboard
from src.bot.keyboards.artistyar_retry_keyboard import artistyar_retry_keyboard

from src.services.course_service import CourseService
from src.database.models.course import ProductDeliveryType
from src.database.models.payment import Payment
from src.services.payment_service import PaymentService
from src.services.payment_card_service import PaymentCardService
from src.services.discount_code_service import DiscountCodeService
from src.services.referral_service import ReferralService
from src.services.enrollment_service import EnrollmentService
from src.services.profile_service import ProfileService
from src.services.license_service import LicenseService
from src.services.artistyar_service import ArtistYarService
from src.services.payment_delivery_service import PaymentDeliveryService
from src.services.admin_log_service import AdminLogService
from src.services.legacy_import_service import LegacyImportService
from src.core.constants import admin_actions
from src.core.config.settings import get_settings

from src.database.repositories.telegram_repository import TelegramRepository
from src.database.repositories.license_repository import LicenseRepository


router = Router()

course_service = CourseService()
payment_service = PaymentService()
payment_card_service = PaymentCardService()
discount_code_service = DiscountCodeService()
referral_service = ReferralService()
enrollment_service = EnrollmentService()
profile_service = ProfileService()
license_service = LicenseService()
artistyar_service = ArtistYarService()
telegram_repository = TelegramRepository()
payment_delivery_service = PaymentDeliveryService(
    payment_service=payment_service,
    enrollment_service=enrollment_service,
    license_service=license_service,
    artistyar_service=artistyar_service,
    referral_service=referral_service,
    telegram_repository=telegram_repository,
)
license_repository = LicenseRepository()
admin_log_service = AdminLogService()
legacy_import_service = LegacyImportService()

settings = get_settings()

PHONE_PATTERN = re.compile(r"^09\d{9}$")


WINDOWS_DOWNLOAD_URL = "https://app.spotplayer.ir/assets/bin/spotplayer/setup.exe"
MAC_DOWNLOAD_URL = "https://app.spotplayer.ir/assets/bin/spotplayer/setup.dmg"


def _payment_instructions_text(final_price: int, card, original_price: int | None = None) -> str:
    """Shared payment-card message for both the plain and discounted
    purchase paths, so the two flows never drift out of sync."""

    discount_line = (
        f"\n💸 قیمت اصلی: {original_price:,} تومان\n"
        if original_price is not None and original_price != final_price
        else ""
    )

    return f"""
💳 اطلاعات پرداخت
{discount_line}
مبلغ قابل پرداخت:
{final_price:,} تومان

شماره کارت:
{card.card_number}

به نام:
{card.card_holder}

پس از واریز، لطفاً عکس یا فایل رسید پرداخت را همینجا ارسال کنید.
"""


async def _has_contact_info(user) -> bool:
    return bool(user.full_name) and bool(user.phone)


async def _begin_direct_purchase(target, state: FSMContext, db, course_id: int):
    """The actual "show payment card, wait for receipt" step - shared by
    the plain buy flow and by whatever flow resumes after collecting a
    first-time buyer's contact info."""

    course = course_service.get_course_by_id(db, course_id)

    if not course:
        await target.answer("دوره پیدا نشد.")
        return

    card = payment_card_service.get_active_card(db)

    if not card:
        await target.answer(
            "⚠️ در حال حاضر امکان پرداخت وجود ندارد. "
            "لطفاً با پشتیبانی تماس بگیرید."
        )
        return

    # Reset any stale discount data from a previous attempt in this
    # conversation - the plain "buy" path is always at full price.
    await state.update_data(
        course_id=course_id,
        discount_code_id=None,
        discount_amount=0,
        final_amount=course.price,
    )
    await state.set_state(PaymentState.waiting_receipt)

    await target.answer(text=_payment_instructions_text(course.price, card))


async def _begin_discount_entry(target, state: FSMContext, db, course_id: int):

    course = course_service.get_course_by_id(db, course_id)

    if not course:
        await target.answer("دوره پیدا نشد.")
        return

    await state.update_data(course_id=course_id)
    await state.set_state(PaymentState.waiting_discount_code)

    await target.answer("🎁 کد تخفیف خود را ارسال کنید:")


async def _start_purchase_or_collect_contact_info(
    callback: CallbackQuery,
    state: FSMContext,
    db,
    course_id: int,
    pending_action: str,
):
    """Common entry gate for both "💳 خرید دوره" and "🎁 دارم کد تخفیف":
    a first-time buyer is asked for their name and phone number before
    anything else, since neither was ever collected at /start. Returning
    buyers (who already have both on file) skip straight through."""

    course = course_service.get_course_by_id(db, course_id)

    if not course:
        await callback.answer("دوره پیدا نشد", show_alert=True)
        return

    user = profile_service.get_profile(db=db, telegram_id=str(callback.from_user.id))

    if not user:
        await callback.answer("❌ کاربر پیدا نشد. لطفاً ابتدا /start را بزنید.", show_alert=True)
        return

    if await _has_contact_info(user):

        if pending_action == "discount":
            await _begin_discount_entry(callback.message, state, db, course_id)
        else:
            await _begin_direct_purchase(callback.message, state, db, course_id)

        await callback.answer()
        return

    await state.update_data(course_id=course_id, pending_purchase_action=pending_action)
    await state.set_state(RegistrationState.full_name)

    await callback.message.answer(
        "برای ادامه‌ی خرید، لازمه چند تا اطلاعات ازتون بگیریم (فقط یک‌بار).\n\n"
        "لطفاً نام و نام خانوادگی خودتون رو ارسال کنید:"
    )

    await callback.answer()


@router.message(RegistrationState.full_name)
async def registration_get_full_name(message: Message, state: FSMContext):

    full_name = (message.text or "").strip()

    if len(full_name) < 3:
        await message.answer("❌ لطفاً نام کامل خودتون رو ارسال کنید:")
        return

    await state.update_data(full_name=full_name)
    await state.set_state(RegistrationState.phone)

    await message.answer("📱 شماره موبایل خودتون رو ارسال کنید (مثال: 09121234567):")


@router.message(RegistrationState.phone)
async def registration_get_phone(message: Message, state: FSMContext, db):

    phone = (message.text or "").strip()

    if not PHONE_PATTERN.match(phone):
        await message.answer(
            "❌ فرمت شماره موبایل درست نیست. به شکل 09121234567 ارسال کنید:"
        )
        return

    data = await state.get_data()

    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))

    if not user:
        await message.answer("❌ کاربر پیدا نشد. لطفاً ابتدا /start را بزنید.")
        await state.clear()
        return

    existing_owner = profile_service.get_profile_by_phone(db, phone)

    if existing_owner and existing_owner.id != user.id:

        legacy_user = legacy_import_service.find_unlinked_by_phone(db, phone)

        if legacy_user and legacy_user.id == existing_owner.id:
            # This phone belongs to a pre-imported (pre-bot) student
            # record that was never linked to a Telegram account -
            # move their purchase history onto this live account.
            legacy_import_service.merge_into_live_user(db, legacy_user, user)
        else:
            await message.answer(
                "❌ این شماره قبلاً برای حساب دیگری ثبت شده. لطفاً شماره دیگری ارسال کنید:"
            )
            return

    profile_service.update_contact_info(
        db=db,
        user=user,
        full_name=data.get("full_name", user.full_name),
        phone=phone,
    )

    course_id = data.get("course_id")
    pending_action = data.get("pending_purchase_action")

    await message.answer("✅ اطلاعات شما ثبت شد.")

    if pending_action == "discount":
        await _begin_discount_entry(message, state, db, course_id)
    else:
        await _begin_direct_purchase(message, state, db, course_id)


@router.callback_query(F.data.startswith("buy_"))
async def buy_course(
    callback: CallbackQuery,
    state: FSMContext,
    db,
):
    """
    Step 1 of the purchase flow: show the payment card and ask the
    student to send their payment receipt. No payment record is
    created yet - it is only created once a receipt is actually sent.
    """

    course_id = int(callback.data.replace("buy_", ""))

    await _start_purchase_or_collect_contact_info(callback, state, db, course_id, "buy")


@router.callback_query(F.data.startswith("discount_"))
async def discount_code_start(
    callback: CallbackQuery,
    state: FSMContext,
    db,
):
    """
    Entry point of the optional discount-code path: asks the student to
    type a code before the payment card is shown.
    """

    course_id = int(callback.data.replace("discount_", ""))

    await _start_purchase_or_collect_contact_info(callback, state, db, course_id, "discount")


@router.message(PaymentState.waiting_discount_code)
async def discount_code_apply(
    message: Message,
    state: FSMContext,
    db,
):
    """
    Validates the entered code and, if valid, reserves a usage slot and
    moves the student straight into the receipt-upload step at the
    discounted price. On failure, stays in the same state so the
    student can retry or fix a typo.
    """

    data = await state.get_data()
    course_id = data.get("course_id")

    course = course_service.get_course_by_id(db, course_id)

    if not course:
        await message.answer("❌ خطایی رخ داد، لطفاً دوباره از منو اقدام کنید.")
        await state.clear()
        return

    card = payment_card_service.get_active_card(db)

    if not card:
        await message.answer(
            "⚠️ در حال حاضر امکان پرداخت وجود ندارد. "
            "لطفاً با پشتیبانی تماس بگیرید."
        )
        await state.clear()
        return

    discount_code, final_price, discount_amount, error = discount_code_service.validate(
        db=db,
        raw_code=message.text or "",
        price=course.price,
    )

    if error:
        await message.answer(f"{error}\nلطفاً کد را دوباره بفرستید یا از /start استفاده کنید.")
        return

    discount_code_service.reserve_usage(db, discount_code)

    await state.update_data(
        discount_code_id=discount_code.id,
        discount_amount=discount_amount,
        final_amount=final_price,
    )
    await state.set_state(PaymentState.waiting_receipt)

    await message.answer(
        f"✅ کد تخفیف اعمال شد ({discount_amount:,} تومان تخفیف).\n"
        + _payment_instructions_text(final_price, card, original_price=course.price)
    )


@router.message(
    PaymentState.waiting_receipt,
    F.photo | F.document,
)
async def receive_receipt(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db,
):
    """
    Step 2: student sent their receipt. Store it as a pending payment
    and notify the owner for manual review. No access is granted here.
    """

    data = await state.get_data()
    course_id = data.get("course_id")
    discount_code_id = data.get("discount_code_id")
    discount_amount = data.get("discount_amount") or 0

    course = course_service.get_course_by_id(db, course_id)

    if not course:
        await message.answer("❌ خطایی رخ داد، لطفاً دوباره از منو اقدام کنید.")
        await state.clear()
        return

    user = profile_service.get_profile(
        db=db,
        telegram_id=str(message.from_user.id),
    )

    if not user:
        await message.answer("❌ کاربر پیدا نشد. لطفاً ابتدا /start را بزنید.")
        await state.clear()
        return

    file_id = (
        message.photo[-1].file_id
        if message.photo
        else message.document.file_id
    )

    final_amount = data.get("final_amount") or course.price
    web_payment_id = data.get("web_payment_id")
    if web_payment_id:
        payment = (
            db.query(Payment)
            .filter(
                Payment.id == int(web_payment_id),
                Payment.user_id == user.id,
                Payment.status == "pending",
            )
            .first()
        )
        if not payment:
            await message.answer("❌ سفارش وب پیدا نشد یا قبلاً بررسی شده است.")
            await state.clear()
            return
        payment.receipt_file_id = file_id
        payment.admin_notes = "سفارش وب — رسید در ربات دریافت شد؛ در انتظار تأیید"
        db.commit()
        db.refresh(payment)
    else:
        payment = payment_service.create_pending(
            db=db,
            user_id=user.id,
            course_id=course_id,
            amount=final_amount,
            receipt_file_id=file_id,
            discount_code_id=discount_code_id,
            discount_amount=discount_amount,
        )

    await state.clear()

    await message.answer(
        "✅ رسید شما دریافت شد.\n"
        "پس از بررسی توسط ادمین، نتیجه به شما اطلاع داده می‌شود."
    )

    discount_line = (
        f"🎁 کد تخفیف: {discount_amount:,} تومان تخفیف اعمال شده\n"
        if discount_code_id
        else ""
    )

    admin_caption = f"""
🧾 رسید پرداخت جدید

👤 نام: {user.full_name}
📱 شماره تماس: {user.phone or "ثبت نشده"}
🎵 دوره: {course.title}
{discount_line}💳 مبلغ: {payment.amount:,} تومان
🆔 شماره پرداخت: {payment.id}
"""

    if message.photo:

        await bot.send_photo(
            chat_id=settings.OWNER_ID,
            photo=file_id,
            caption=admin_caption,
            reply_markup=payment_review_keyboard(payment.id),
        )

    else:

        await bot.send_document(
            chat_id=settings.OWNER_ID,
            document=file_id,
            caption=admin_caption,
            reply_markup=payment_review_keyboard(payment.id),
        )


async def _deliver_spotplayer(
    bot: Bot,
    db,
    user,
    telegram_id: str,
    course,
    payment_id: int,
):
    """
    Issues a SpotPlayer license and sends it to the student.
    On failure, notifies the owner with a retry button - the
    payment/enrollment stay valid either way, nothing is lost.
    """

    license_ = await license_service.issue_license(
        db=db,
        user_id=user.id,
        user_full_name=user.full_name,
        user_phone=user.phone,
        product=course,
        payment_id=payment_id,
    )

    if license_.status == "active":

        support_line = (
            f"\n\n🎧 گروه پشتیبانی:\n{course.support_group_link}"
            if course.support_group_link
            else ""
        )

        await bot.send_message(
            chat_id=telegram_id,
            text=f"""
🎓 لایسنس شما آماده شد!

🔑 کلید لایسنس:
{license_.license_key}

💻 دانلود ویندوز:
{WINDOWS_DOWNLOAD_URL}

🍎 دانلود مک:
{MAC_DOWNLOAD_URL}

پس از نصب نرم‌افزار SpotPlayer، کلید لایسنس بالا را وارد کنید.{support_line}
""",
        )

    else:

        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "✅ پرداخت شما تایید شد.\n"
                "در صدور خودکار لایسنس مشکلی پیش آمد؛ "
                "پشتیبانی به‌زودی به‌صورت دستی برای شما ارسال می‌کند."
            ),
        )

        await bot.send_message(
            chat_id=settings.OWNER_ID,
            text=(
                f"⚠️ صدور لایسنس SpotPlayer برای «{course.title}» "
                f"(هنرجو: {user.full_name}) ناموفق بود:\n{license_.error_message}"
            ),
            reply_markup=license_retry_keyboard(license_.id),
        )


async def _deliver_artistyar(
    bot: Bot,
    db,
    user_id: int,
    telegram_id: str,
    course,
):
    """
    Generates/reuses one-time invite links for every enabled channel of
    an ArtistYar-type product and sends them to the student. Channels
    that fail are reported to the owner with a retry button - calling
    the retry re-attempts only the channels that are still missing a link.
    """

    results = await artistyar_service.deliver_channels(
        bot=bot,
        db=db,
        user_id=user_id,
        product=course,
    )

    successful = [r for r in results if r["invite_link"]]
    failed = [r for r in results if not r["invite_link"]]

    if successful:

        links_text = "\n".join(
            f"📢 {r['channel_name']}:\n{r['invite_link']}"
            for r in successful
        )

        await bot.send_message(
            chat_id=telegram_id,
            text=f"""
✅ لینک‌های دسترسی شما:

{links_text}

⚠️ این لینک‌ها فقط یک‌بار قابل استفاده هستند.
""",
        )

    if failed:

        failed_names = "، ".join(r["channel_name"] for r in failed)

        await bot.send_message(
            chat_id=settings.OWNER_ID,
            text=(
                f"⚠️ ساخت لینک دعوت برای کانال‌های «{failed_names}» "
                f"(محصول: {course.title}) ناموفق بود. "
                "بعد از رفع مشکل (مثلاً ادمین‌کردن ربات در کانال)، دوباره تلاش کنید."
            ),
            reply_markup=artistyar_retry_keyboard(user_id, course.id),
        )


@router.callback_query(F.data.startswith("pay_approve_"))
async def approve_payment(
    callback: CallbackQuery,
    bot: Bot,
    db,
):

    if callback.from_user.id != settings.OWNER_ID:
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    payment_id = int(callback.data.replace("pay_approve_", ""))

    existing = payment_service.get_by_id(db, payment_id)

    if not existing:
        await callback.answer("پرداخت پیدا نشد", show_alert=True)
        return

    if existing.status != "pending":
        await callback.answer("این پرداخت قبلاً بررسی شده است.", show_alert=True)
        return

    delivery = await payment_delivery_service.approve_and_deliver(
        db=db,
        payment_id=payment_id,
        admin_telegram_id=callback.from_user.id,
        bot=bot,
        notify_student=True,
    )
    if not delivery:
        await callback.answer("پرداخت پیدا نشد", show_alert=True)
        return
    payment = delivery.payment
    course_for_log = delivery.course

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.PAYMENT_APPROVE,
        f"پرداخت #{payment.id} برای دوره «{course_for_log.title if course_for_log else payment.course_id}» "
        f"به مبلغ {payment.amount:,} تومان تایید شد",
    )

    rewarded_referral = delivery.referral_rewarded

    if rewarded_referral:

        admin_log_service.log(
            db, "system", admin_actions.REFERRAL_REWARD,
            f"پاداش معرفی دوست برای کاربر #{rewarded_referral.referrer_id} صادر شد "
            f"(کد تخفیف #{rewarded_referral.reward_discount_code_id})",
        )

        referrer_telegram_account = telegram_repository.get_by_user_id(
            db, rewarded_referral.referrer_id
        )
        reward_code = discount_code_service.get_by_id(
            db, rewarded_referral.reward_discount_code_id
        )

        if referrer_telegram_account and reward_code:

            await bot.send_message(
                chat_id=referrer_telegram_account.telegram_id,
                text=(
                    "🎉 دوستی که شما دعوت کرده بودید خریدش رو انجام داد!\n\n"
                    f"کد تخفیف {reward_code.value}٪ زیر رو به‌عنوان پاداش دریافت کردید:\n"
                    f"🎁 {reward_code.code}\n\n"
                    "این کد رو موقع خرید بعدی‌تون وارد کنید."
                ),
            )

    if delivery.license and delivery.license.status != "active":
        await bot.send_message(
            chat_id=settings.OWNER_ID,
            text=(
                f"⚠️ صدور لایسنس برای «{delivery.course.title}» ناموفق بود.\n"
                f"پرداخت #{payment.id} — کاربر {delivery.user.phone or delivery.user.id}\n"
                "از گزینه تلاش مجدد لایسنس استفاده کنید."
            ),
            reply_markup=license_retry_keyboard(delivery.license.id),
        )

    failed_channels = [item for item in delivery.channel_deliveries if not item.invite_link]
    if failed_channels:
        failed_names = "، ".join(item.channel_name for item in failed_channels)
        await bot.send_message(
            chat_id=settings.OWNER_ID,
            text=(
                f"⚠️ ساخت لینک دعوت برای «{failed_names}» "
                f"(محصول: {delivery.course.title}) ناموفق بود."
            ),
            reply_markup=artistyar_retry_keyboard(delivery.user.id, delivery.course.id),
        )

    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ تایید شد."
    )

    await callback.answer("تایید شد ✅")


@router.callback_query(F.data.startswith("license_retry_"))
async def retry_license(
    callback: CallbackQuery,
    bot: Bot,
    db,
):
    """
    Owner-triggered retry for a SpotPlayer license that previously failed.
    """

    if callback.from_user.id != settings.OWNER_ID:
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    license_id = int(callback.data.replace("license_retry_", ""))

    failed_license = license_repository.get_by_id(db, license_id)

    if not failed_license:
        await callback.answer("لایسنس پیدا نشد", show_alert=True)
        return

    if failed_license.status == "active":
        await callback.answer("این لایسنس قبلاً با موفقیت صادر شده است.", show_alert=True)
        return

    course = course_service.get_course_by_id(db, failed_license.product_id)
    user = profile_service.get_profile_by_id(db, failed_license.user_id)
    payment = payment_service.get_by_id(db, failed_license.payment_id) if failed_license.payment_id else None

    if not course or not user or not payment or payment.status != "approved":
        await callback.answer("اطلاعات لازم برای تلاش مجدد پیدا نشد.", show_alert=True)
        return

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.LICENSE_RETRY,
        f"تلاش مجدد صدور لایسنس SpotPlayer برای «{course.title}» (هنرجو: {user.full_name})",
    )

    await callback.answer("در حال تلاش مجدد... ⏳")

    delivery = await payment_delivery_service.deliver_approved_payment(
        bot=bot,
        db=db,
        payment=payment,
        notify_student=True,
        reward_referral=False,
    )

    await callback.message.edit_text(
        callback.message.text + (
            "\n\n✅ لایسنس با موفقیت صادر شد."
            if delivery.license and delivery.license.status == "active"
            else "\n\n⚠️ تلاش مجدد انجام شد، اما صدور لایسنس هنوز ناموفق است."
        )
    )


@router.callback_query(F.data.startswith("artistyar_retry_"))
async def retry_artistyar(
    callback: CallbackQuery,
    bot: Bot,
    db,
):
    """
    Owner-triggered retry for ArtistYar channels that previously failed.
    Only the channels still missing a link are attempted again.
    """

    if callback.from_user.id != settings.OWNER_ID:
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    parts = callback.data.replace("artistyar_retry_", "").split("_")
    user_id, product_id = int(parts[0]), int(parts[1])

    course = course_service.get_course_by_id(db, product_id)
    payment = (
        db.query(Payment)
        .filter(
            Payment.user_id == user_id,
            Payment.course_id == product_id,
            Payment.status == "approved",
        )
        .order_by(Payment.id.desc())
        .first()
    )

    if not course or not payment:
        await callback.answer("اطلاعات لازم برای تلاش مجدد پیدا نشد.", show_alert=True)
        return

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.ARTISTYAR_RETRY,
        f"تلاش مجدد ساخت لینک دعوت ArtistYar برای «{course.title}» (کاربر #{user_id})",
    )

    await callback.answer("در حال تلاش مجدد... ⏳")

    delivery = await payment_delivery_service.deliver_approved_payment(
        bot=bot,
        db=db,
        payment=payment,
        notify_student=True,
        reward_referral=False,
    )
    failed_channels = [item for item in delivery.channel_deliveries if not item.invite_link]

    await callback.message.edit_text(
        callback.message.text + (
            "\n\n✅ لینک‌های باقی‌مانده ساخته شد."
            if not failed_channels
            else "\n\n⚠️ تلاش مجدد انجام شد، اما بعضی لینک‌ها هنوز ساخته نشدند."
        )
    )


@router.callback_query(F.data.startswith("pay_reject_"))
async def reject_payment(
    callback: CallbackQuery,
    bot: Bot,
    db,
):

    if callback.from_user.id != settings.OWNER_ID:
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    payment_id = int(callback.data.replace("pay_reject_", ""))

    existing = payment_service.get_by_id(db, payment_id)

    if not existing:
        await callback.answer("پرداخت پیدا نشد", show_alert=True)
        return

    if existing.status != "pending":
        await callback.answer("این پرداخت قبلاً بررسی شده است.", show_alert=True)
        return

    payment = payment_service.reject(
        db=db,
        payment_id=payment_id,
        admin_telegram_id=callback.from_user.id,
    )

    if payment.discount_code_id:
        # Rejecting a receipt should not permanently waste the
        # student's discount-code usage slot.
        discount_code_service.release_usage_by_id(db, payment.discount_code_id)

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.PAYMENT_REJECT,
        f"پرداخت #{payment.id} به مبلغ {payment.amount:,} تومان رد شد",
    )

    telegram_account = telegram_repository.get_by_user_id(db, payment.user_id)

    if telegram_account:

        await bot.send_message(
            chat_id=telegram_account.telegram_id,
            text=(
                "❌ پرداخت شما تایید نشد.\n"
                "لطفاً مجدداً فیش صحیح ارسال نمایید یا با پشتیبانی تماس بگیرید."
            ),
        )

    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n❌ رد شد."
    )

    await callback.answer("رد شد ❌")
