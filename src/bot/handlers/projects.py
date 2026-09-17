from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session

from src.core.config.settings import get_settings
from src.services.project_marketplace_service import ProjectMarketplaceService, ProjectMarketplaceError

router = Router(name="projects")
service = ProjectMarketplaceService()
settings = get_settings()


@router.message(Command("projects"))
async def list_projects(message: Message, db: Session):
    projects = service.list_published(db, limit=8)
    if not projects:
        await message.answer("📭 فعلاً پروژهٔ فعالی برای هنرجوها ثبت نشده است.")
        return
    lines = ["🎯 پروژه‌های فعال راه‌یار\n"]
    for project in projects:
        budget = f"تا {project.budget_max:,} تومان" if project.budget_max else "بودجه توافقی"
        lines.append(f"#{project.id} · {project.title}\n{project.category} · {budget}\n{project.description[:240]}\n")
    lines.append("برای معرفی مهارتت به تیم راه‌یار، /profile را تکمیل کن.")
    await message.answer("\n".join(lines))


@router.message(Command("project"))
async def submit_project(message: Message, db: Session):
    raw = (message.text or "").partition(" ")[2].strip()
    parts = [part.strip() for part in raw.split("|")]
    if len(parts) < 4:
        await message.answer("برای ثبت پروژه این قالب را بفرست:\n/project عنوان | دسته‌بندی | راه تماس | توضیحات پروژه")
        return
    title, category, contact, description = parts[:4]
    try:
        project = service.create_project(db, employer_name=message.from_user.full_name if message.from_user else "کارفرما", employer_contact=contact, title=title, category=category, description=description)
    except ProjectMarketplaceError:
        await message.answer("❌ اطلاعات پروژه کامل نیست. قالب نمونه را رعایت کن.")
        return
    await message.answer(f"✅ پروژهٔ #{project.id} ثبت شد و پس از بررسی تیم راه‌یار منتشر می‌شود.")
    if settings.OWNER_ID:
        try:
            await message.bot.send_message(settings.OWNER_ID, f"📥 پروژهٔ جدید #{project.id}\n{project.title}\nدسته: {project.category}\nتماس: {project.employer_contact}\n\nبرای بررسی در پنل مدیریت اقدام کن.")
        except Exception:
            pass
