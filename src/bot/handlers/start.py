from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from src.services.telegram_service import TelegramService
from src.services.referral_service import ReferralService
from src.bot.keyboards.main_menu import get_main_menu


router = Router()

telegram_service = TelegramService()
referral_service = ReferralService()

REFERRAL_PAYLOAD_PREFIX = "ref_"



@router.message(Command("start"))
async def start_handler(
    message: Message,
    command: CommandObject,
    db
):

    user, is_new = telegram_service.get_or_create_user(
        db=db,
        telegram_id=str(message.from_user.id),
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )

    if is_new and command.args and command.args.startswith(REFERRAL_PAYLOAD_PREFIX):

        referrer_telegram_id = command.args[len(REFERRAL_PAYLOAD_PREFIX):]

        # Silently ignored if the code doesn't resolve to a real user -
        # an invalid invite link should never block registration.
        referral_service.create_referral_if_eligible(
            db=db,
            referrer_telegram_id=referrer_telegram_id,
            referred_user_id=user.id,
        )


    await message.answer(
        f"سلام {user.full_name} 👋\n"
        "به آکادمی راه‌یار خوش آمدید.",
        reply_markup=get_main_menu(
            user.role
        )
    )