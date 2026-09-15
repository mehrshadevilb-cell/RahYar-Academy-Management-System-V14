"""Student-facing read-only assistant grounded in catalog + AI Agent knowledge."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from src.ai.provider_router import AIProviderError, AIProviderRouter
from src.core.config.settings import get_settings
from src.database.models.course import ProductDeliveryType
from src.services.course_service import CourseService
from src.services.online_course_service import OnlineCourseService

MAX_USER_MESSAGE_CHARS = 1000
MAX_REPLY_CHARS = 3500

BOT_GUIDE_FA = """
راهنمای منوی اصلی ربات راه‌یار:
- 📚 دوره ها: دوره‌های دیجیتال قابل خرید.
- 🎓 دوره های من: خریدها و دسترسی‌های کاربر.
- 🎼 کلاس آنلاین: کلاس‌های خصوصی زنده و رزرو.
- 📝 تکالیف: تکالیف و ارسال پاسخ.
- 📈 پیشرفت من: وضعیت پیشرفت کلاس.
- 🆘 پشتیبانی: ثبت درخواست برای مدیریت.
""".strip()

SYSTEM_PROMPT_FA = """
تو دستیار آموزشی آکادمی راه‌یار هستی. پاسخ را فارسی، کوتاه و کاربردی بده.
دانش تو توسط AI Agent از پیام‌های گروه آکادمی و منابع رسمی Waves و iZotope Ozone جمع‌آوری،
ترجمه و به‌روزرسانی می‌شود. برای اطلاعات متغیر مثل قیمت و وضعیت پرداخت فقط از داده‌های فعلی
ربات استفاده کن. اگر چیزی در context نیست حدس نزن.
هرگز اطلاعات خصوصی کاربران، اطلاعات پرداخت، کلید API یا داده محرمانه را بازگو نکن.
اگر سؤال درباره پرداخت/شکایت/دسترسی اختصاصی است، کاربر را به «🆘 پشتیبانی» ارجاع بده.
"""


class ChatAssistantError(RuntimeError):
    pass


class ChatAssistantService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.router = AIProviderRouter()
        self.course_service = CourseService()
        self.online_course_service = OnlineCourseService()
        self._recent_messages: dict[str, deque[float]] = defaultdict(deque)

    def _check_enabled(self) -> None:
        if not self.settings.CHAT_ASSISTANT_ENABLED:
            raise ChatAssistantError("disabled")
        if not self.router.providers():
            raise ChatAssistantError("not_configured")

    def _check_rate_limit(self, telegram_id: str) -> None:
        limit = self.settings.CHAT_ASSISTANT_MAX_MESSAGES_PER_HOUR
        if limit <= 0:
            return
        now = time.time()
        window = self._recent_messages[telegram_id]
        while window and now - window[0] > 3600:
            window.popleft()
        if len(window) >= limit:
            raise ChatAssistantError("تعداد پیام‌های شما به دستیار در این ساعت به حد مجاز رسیده است. لطفاً کمی بعد دوباره تلاش کنید یا از «🆘 پشتیبانی» استفاده کنید.")
        window.append(now)

    def _catalog_context(self, db: Session) -> str:
        lines = ["دوره‌های دیجیتال فعال فعلی:"]
        courses = self.course_service.get_courses(db)
        if not courses:
            lines.append("- فعلاً دوره دیجیتالی فعالی نیست.")
        for course in courses:
            price = f"{course.price:,} تومان" if course.price else "رایگان"
            delivery = "SpotPlayer" if course.delivery_type == ProductDeliveryType.SPOTPLAYER else "کانال تلگرام"
            lines.append(f"- {course.title} | {price} | تحویل: {delivery}")
        lines.append("\nکلاس‌های آنلاین فعال فعلی:")
        online_courses = self.online_course_service.get_active_courses(db)
        if not online_courses:
            lines.append("- فعلاً کلاس آنلاینی تعریف نشده است.")
        for oc in online_courses:
            monthly = f"{oc.monthly_price:,} تومان" if oc.monthly_price else "-"
            term = f"{oc.term_price:,} تومان" if oc.term_price else "-"
            lines.append(f"- {oc.name} | ماهانه: {monthly} ({oc.monthly_sessions} جلسه) | ترمی: {term} ({oc.term_sessions} جلسه)")
        return "\n".join(lines)

    def _request_model(self, messages: list[dict]) -> str:
        try:
            data = self.router.chat(messages, temperature=0.3, max_tokens=700)
            return str(data["choices"][0]["message"]["content"]).strip()
        except AIProviderError as exc:
            if exc.retryable:
                raise ChatAssistantError("provider_rate_limited" if exc.retry_after else "provider_unavailable") from exc
            raise ChatAssistantError("provider_unavailable") from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise ChatAssistantError("provider_unavailable") from exc

    def answer(self, db: Session, telegram_id: str, user_message: str) -> str:
        self._check_enabled()
        text = (user_message or "").strip()
        if not text:
            raise ChatAssistantError("empty_message")
        text = text[:MAX_USER_MESSAGE_CHARS]
        self._check_rate_limit(telegram_id)
        from src.services.ai_agent_knowledge_runtime import AIAgentKnowledgeRuntime
        knowledge = AIAgentKnowledgeRuntime().context(db, limit=12)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_FA},
            {"role": "system", "content": BOT_GUIDE_FA},
            {"role": "system", "content": self._catalog_context(db)},
            {"role": "system", "content": "دانش جمع‌آوری و پالایش‌شده توسط AI Agent:\n" + (knowledge or "هنوز مطلب آموزشی ثبت نشده است.")},
            {"role": "user", "content": text},
        ]
        return self._request_model(messages)[:MAX_REPLY_CHARS]
