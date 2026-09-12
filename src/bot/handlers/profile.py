from aiogram import Router
from aiogram.types import Message

from src.services.profile_service import ProfileService



router = Router()



profile_service = ProfileService()



@router.message(
    lambda message: message.text == "👤 پروفایل"
)
async def profile_handler(
    message: Message,
    db
):


    user = profile_service.get_profile(
        db=db,
        telegram_id=str(
            message.from_user.id
        ),
    )



    if not user:


        await message.answer(
            "❌ پروفایل شما پیدا نشد."
        )


        return



    role_text = (
        "مدیر"
        if user.role.value == "admin"
        else
        "هنرجو"
    )



    await message.answer(

        f"""
👤 پروفایل شما


نام:
{user.full_name}


نقش:
{role_text}


وضعیت:
{"فعال" if user.is_active else "غیرفعال"}


تاریخ عضویت:
{user.created_at.strftime("%Y-%m-%d")}

"""
    )


