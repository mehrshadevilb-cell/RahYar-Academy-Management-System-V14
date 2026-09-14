from aiogram import F, Router
from aiogram.types import Message

from src.services.profile_service import ProfileService
from src.services.progress_service import ProgressService

router = Router()
profile_service = ProfileService()
progress_service = ProgressService()


@router.message(F.text == "📈 پیشرفت من")
async def student_progress(message: Message, db):
    user = profile_service.get_profile(db=db, telegram_id=str(message.from_user.id))
    if not user:
        await message.answer("❌ لطفاً ابتدا /start را بزنید.")
        return

    snapshot = progress_service.get_snapshot(db, user.id)
    text = progress_service.format_persian(snapshot)

    if len(text) > 4000:
        text = text[:3990] + "\n…"

    await message.answer(text)
