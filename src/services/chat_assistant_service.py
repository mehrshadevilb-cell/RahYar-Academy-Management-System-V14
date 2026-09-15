"""Student-facing read-only assistant grounded in catalog + academy knowledge."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from src.core.config.settings import get_settings
from src.database.models.course import ProductDeliveryType
from src.services.course_service import CourseService
from src.services.online_course_service import OnlineCourseService
from src.services.knowledge_service import KnowledgeService

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
می‌توانی درباره موسیقی، تولید صدا، میکس، مسترینگ، Waves، iZotope Ozone و مطالب آموزشی
ثبت‌شده از گروه آکادمی پاسخ بدهی. برای اطلاعات متغیر مثل قیمت و وضعیت پرداخت فقط از داده‌های
فعلی ربات استفاده کن. اگر چیزی در context نیست حدس نزن.
هرگز اطلاعات خصوصی کاربران، اطلاعات پرداخت، کلید API یا داده محرمانه را بازگو نکن.
اگر سؤال درباره پرداخت/شکایت/دسترسی اختصاصی است، کاربر را به «🆘 پشتیبانی» ارجاع بده.
"""


class ChatAssistantError(RuntimeError):
    pass


class ChatAssistantService:
    _AGENTROUTER_HEADERS = {"Originator": "codex_cli_rs", "Version": "0.101.0", "User-Agent": "codex_cli_rs/0.101.0 (Linux; x86_64) RahYar-Chat/1.0"}

    def __init__(self) -> None:
        self.settings = get_settings()
        self.course_service = CourseService()
        self.online_course_service = OnlineCourseService()
        self.knowledge_service = KnowledgeService()
        self._recent_messages: dict[str, deque[float]] = defaultdict(deque)

    def _check_enabled(self) -> None:
        if not self.settings.CHAT_ASSISTANT_ENABLED:
            raise ChatAssistantError("disabled")
        if not self.settings.effective_chat_api_key:
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

    def _provider_headers(self) -> dict[str, str]:
        key = self.settings.effective_chat_api_key or ""
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "RahYar-ChatAssistant/1.0"}
        if (urlparse(self.settings.effective_chat_base_url).hostname or "").lower().endswith("agentrouter.org"):
            headers.update(self._AGENTROUTER_HEADERS)
        return headers

    def _request_model(self, messages: list[dict]) -> str:
        request = urllib.request.Request(
            self.settings.effective_chat_base_url.rstrip("/") + "/chat/completions",
            data=json.dumps({"model": self.settings.effective_chat_model, "messages": messages, "temperature": 0.3, "max_tokens": 700}).encode("utf-8"),
            headers=self._provider_headers(), method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.CHAT_ASSISTANT_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as exc:
            raise ChatAssistantError(f"provider_http_{exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ChatAssistantError("provider_unavailable") from exc

    def answer(self, db: Session, telegram_id: str, user_message: str) -> str:
        self._check_enabled()
        text = (user_message or "").strip()
        if not text:
            raise ChatAssistantError("empty_message")
        text = text[:MAX_USER_MESSAGE_CHARS]
        self._check_rate_limit(telegram_id)
        knowledge = self.knowledge_service.context(db, limit=12)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_FA},
            {"role": "system", "content": BOT_GUIDE_FA},
            {"role": "system", "content": self._catalog_context(db)},
            {"role": "system", "content": "دانش آکادمی و منابع رسمی جمع‌آوری‌شده:\n" + (knowledge or "هنوز مطلب آموزشی ثبت نشده است.")},
            {"role": "user", "content": text},
        ]
        return self._request_model(messages)[:MAX_REPLY_CHARS]
