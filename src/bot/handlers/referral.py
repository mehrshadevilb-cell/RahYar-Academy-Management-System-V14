from aiogram import Router, F, Bot
from aiogram.types import Message

from src.services.profile_service import ProfileService
from src.services.referral_service import ReferralService, REFERRAL_REWARD_PERCENTAGE
from src.database.models.referral import ReferralStatus


router = Router()

profile_service = ProfileService()
referral_service = ReferralService()


@router.message(F.text == "🎁 دعوت از دوستان")
async def referral_menu(message: Message, bot: Bot, db):

    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))

    if not user:
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    bot_info = await bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start=ref_{message.from_user.id}"

    referrals = referral_service.get_by_referrer(db, user.id)
    rewarded_count = sum(1 for r in referrals if r.status == ReferralStatus.REWARDED)
    pending_count = len(referrals) - rewarded_count

    await message.answer(
        "🎁 دوستان خودتون رو به آکادمی راه‌یار دعوت کنید!\n\n"
        f"به ازای هر دوستی که با لینک شما ثبت‌نام کنه و اولین خریدش رو انجام بده، "
        f"یک کد تخفیف {REFERRAL_REWARD_PERCENTAGE}٪ دریافت می‌کنید.\n\n"
        f"🔗 لینک دعوت شما:\n{invite_link}\n\n"
        f"📊 وضعیت دعوت‌های شما:\n"
        f"✅ پاداش دریافت‌شده: {rewarded_count}\n"
        f"⏳ در انتظار خرید دوست شما: {pending_count}"
    )
