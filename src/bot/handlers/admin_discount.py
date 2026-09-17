from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.states.admin_states import AdminState
from src.bot.keyboards.admin_menu_keyboard import admin_back_button
from src.bot.keyboards.admin_discount_keyboard import (
    admin_discounts_keyboard,
    admin_discount_detail_keyboard,
    admin_discount_type_keyboard,
)
from src.database.models.discount_code import DiscountType
from src.services.discount_code_service import DiscountCodeService
from src.services.admin_log_service import AdminLogService
from src.core.constants import admin_actions
from src.core.admin_access import is_admin_user


router = Router()

discount_code_service = DiscountCodeService()
admin_log_service = AdminLogService()


def _discount_detail_text(code) -> str:

    status = "✅ فعال" if code.is_active else "🚫 غیرفعال"

    type_label = "درصدی" if code.discount_type == DiscountType.PERCENTAGE else "مبلغ ثابت"
    value_label = f"{code.value}٪" if code.discount_type == DiscountType.PERCENTAGE else f"{code.value:,} تومان"
    max_uses_label = str(code.max_uses) if code.max_uses is not None else "نامحدود"
    expires_label = (
        code.expires_at.strftime("%Y-%m-%d") if code.expires_at else "بدون انقضا"
    )

    return f"""
🎁 کد تخفیف: {code.code}

نوع: {type_label}
میزان تخفیف: {value_label}
سقف استفاده: {max_uses_label}
تعداد استفاده‌شده: {code.used_count}
تاریخ انقضا: {expires_label}
وضعیت: {status}
"""


# ---------------- List / view / toggle ----------------

@router.callback_query(F.data == "admin_discounts")
async def admin_discounts_list(callback: CallbackQuery, db):

    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    codes = discount_code_service.get_all(db)

    if not codes:
        await callback.message.edit_text(
            "🎁 هنوز هیچ کد تخفیفی ثبت نشده است.",
            reply_markup=admin_discounts_keyboard(codes),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🎁 کدهای تخفیف:\n(✅ فعال / 🚫 غیرفعال)",
        reply_markup=admin_discounts_keyboard(codes),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("admin_discount_view_"))
async def admin_discount_view(callback: CallbackQuery, db):

    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    code_id = int(callback.data.replace("admin_discount_view_", ""))
    code = discount_code_service.get_by_id(db, code_id)

    if not code:
        await callback.answer("کد تخفیف پیدا نشد", show_alert=True)
        return

    await callback.message.edit_text(
        _discount_detail_text(code),
        reply_markup=admin_discount_detail_keyboard(code),
    )

    await callback.answer()


@router.callback_query(F.data.startswith("admin_discount_toggle_"))
async def admin_discount_toggle(callback: CallbackQuery, db):

    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    code_id = int(callback.data.replace("admin_discount_toggle_", ""))
    code = discount_code_service.toggle_active(db, code_id)

    if not code:
        await callback.answer("کد تخفیف پیدا نشد", show_alert=True)
        return

    admin_log_service.log(
        db, callback.from_user.id, admin_actions.DISCOUNT_CODE_TOGGLE,
        f"وضعیت کد تخفیف «{code.code}» تغییر کرد "
        f"({'فعال' if code.is_active else 'غیرفعال'})",
    )

    await callback.message.edit_text(
        _discount_detail_text(code),
        reply_markup=admin_discount_detail_keyboard(code),
    )

    await callback.answer("وضعیت تغییر کرد ✅")


# ---------------- Creation wizard ----------------

@router.callback_query(F.data == "admin_discount_add")
async def admin_discount_add_start(callback: CallbackQuery, state: FSMContext):

    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    await state.set_state(AdminState.waiting_discount_code_text)

    await callback.message.answer(
        "کد تخفیف را وارد کنید (فقط حروف انگلیسی و عدد، مثلاً SUMMER30):"
    )

    await callback.answer()


@router.message(AdminState.waiting_discount_code_text)
async def admin_discount_add_text(message: Message, state: FSMContext, db):

    if not is_admin_user(message.from_user):
        return

    raw_code = (message.text or "").strip()

    if not raw_code or not raw_code.replace(" ", "").isalnum() or len(raw_code) > 50:
        await message.answer(
            "❌ کد تخفیف باید فقط شامل حروف انگلیسی و عدد باشد (بدون فاصله). دوباره بفرستید:"
        )
        return

    normalized = discount_code_service.normalize_code(raw_code)

    if discount_code_service.code_exists(db, normalized):
        await message.answer(
            "❌ این کد تخفیف قبلاً ثبت شده است. کد دیگری وارد کنید:"
        )
        return

    await state.update_data(discount_code_text=normalized)
    await state.set_state(AdminState.waiting_discount_code_type)

    await message.answer(
        "نوع تخفیف را انتخاب کنید:",
        reply_markup=admin_discount_type_keyboard(),
    )


@router.callback_query(
    AdminState.waiting_discount_code_type,
    F.data.in_({"admin_discount_type_percentage", "admin_discount_type_fixed"}),
)
async def admin_discount_add_type(callback: CallbackQuery, state: FSMContext):

    if not is_admin_user(callback.from_user):
        await callback.answer("⛔️ شما دسترسی ندارید.", show_alert=True)
        return

    discount_type = (
        DiscountType.PERCENTAGE
        if callback.data == "admin_discount_type_percentage"
        else DiscountType.FIXED
    )

    await state.update_data(discount_type=discount_type.value)
    await state.set_state(AdminState.waiting_discount_code_value)

    prompt = (
        "عدد درصد تخفیف را بین ۱ تا ۱۰۰ وارد کنید:"
        if discount_type == DiscountType.PERCENTAGE
        else "مبلغ تخفیف را به تومان و فقط به‌صورت عدد وارد کنید:"
    )

    await callback.message.answer(prompt)

    await callback.answer()


@router.message(AdminState.waiting_discount_code_value)
async def admin_discount_add_value(message: Message, state: FSMContext):

    if not is_admin_user(message.from_user):
        return

    data = await state.get_data()
    discount_type_raw = data.get("discount_type")

    if not discount_type_raw:
        # Defensive fallback - should not normally happen since the type
        # step always sets this before moving into this state.
        await message.answer("لطفاً ابتدا نوع تخفیف را با دکمه‌های بالا انتخاب کنید.")
        return

    raw = (message.text or "").replace(",", "").strip()

    if not raw.isdigit():
        await message.answer("❌ لطفاً فقط عدد بفرستید. دوباره تلاش کنید:")
        return

    value = int(raw)
    discount_type = DiscountType(discount_type_raw)

    if discount_type == DiscountType.PERCENTAGE and not (1 <= value <= 100):
        await message.answer("❌ درصد تخفیف باید بین ۱ تا ۱۰۰ باشد. دوباره بفرستید:")
        return

    if value <= 0:
        await message.answer("❌ مقدار تخفیف باید بزرگ‌تر از صفر باشد. دوباره بفرستید:")
        return

    await state.update_data(discount_value=value)
    await state.set_state(AdminState.waiting_discount_code_max_uses)

    await message.answer(
        "حداکثر تعداد دفعات استفاده از این کد چقدر باشد؟\n"
        "برای نامحدود، عدد 0 را بفرستید."
    )


@router.message(AdminState.waiting_discount_code_max_uses)
async def admin_discount_add_max_uses(message: Message, state: FSMContext):

    if not is_admin_user(message.from_user):
        return

    raw = (message.text or "").strip()

    if not raw.isdigit():
        await message.answer("❌ لطفاً فقط عدد بفرستید (برای نامحدود 0). دوباره تلاش کنید:")
        return

    max_uses = int(raw) or None

    await state.update_data(discount_max_uses=max_uses)
    await state.set_state(AdminState.waiting_discount_code_expiry)

    await message.answer(
        "تاریخ انقضای کد را به فرمت YYYY-MM-DD وارد کنید (مثلاً 2026-12-31).\n"
        "برای بدون تاریخ انقضا، کلمه «ندارد» را بفرستید."
    )


@router.message(AdminState.waiting_discount_code_expiry)
async def admin_discount_add_expiry(message: Message, state: FSMContext, db):

    if not is_admin_user(message.from_user):
        return

    raw = (message.text or "").strip()

    expires_at = None

    if raw not in ("ندارد", "-", "no", "none"):

        try:
            expires_at = datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            await message.answer(
                "❌ فرمت تاریخ نامعتبر است. به شکل YYYY-MM-DD بفرستید "
                "(مثلاً 2026-12-31) یا «ندارد» را ارسال کنید:"
            )
            return

    data = await state.get_data()

    code = discount_code_service.create_code(
        db=db,
        code=data.get("discount_code_text"),
        discount_type=DiscountType(data.get("discount_type")),
        value=data.get("discount_value"),
        max_uses=data.get("discount_max_uses"),
        expires_at=expires_at,
    )

    await state.clear()

    if not code:
        await message.answer(
            "❌ این کد تخفیف همزمان توسط جای دیگری ثبت شد. لطفاً دوباره از ابتدا اقدام کنید.",
            reply_markup=admin_back_button("admin_discounts"),
        )
        return

    admin_log_service.log(
        db, message.from_user.id, admin_actions.DISCOUNT_CODE_CREATE,
        f"کد تخفیف «{code.code}» ساخته شد",
    )

    await message.answer(
        f"✅ کد تخفیف ساخته شد.\n{_discount_detail_text(code)}",
        reply_markup=admin_discount_detail_keyboard(code),
    )
