"""Student-facing chat assistant.

Unlike AIAgentService (src/services/ai_agent_service.py), this service is
strictly read-only: it never writes files, never touches git, and never
executes code. It answers free-text questions from students - "how do I
buy a course", "what does SpotPlayer mean", "where's my license" - and
can point them at the right menu button, using the bot's real, current
product catalog as grounding so it doesn't invent prices or courses that
don't exist.

It is deliberately a separate module from AIAgentService: mixing a
"talks to any student, all day" surface with the AI Developer Agent's
write/commit capability into one class would make the security-critical
agent harder to reason about. Keeping them separate keeps each one's
blast radius small and easy to audit independently.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from src.core.config.settings import get_settings
from src.database.models.course import ProductDeliveryType
from src.services.course_service import CourseService
from src.services.online_course_service import OnlineCourseService

MAX_USER_MESSAGE_CHARS = 1000
MAX_REPLY_CHARS = 3500

# The bot's own navigation, in the bot's own words. This is UI/menu
# copy (like every other Persian string in the handlers), not business
# data, so unlike prices/courses it is not meant to be admin-editable -
# it changes only when the actual menu layout changes in code.
BOT_GUIDE_FA = """
راهنمای منوی اصلی ربات راه‌یار:
- 📚 دوره ها: نمایش دوره‌های دیجیتال قابل خرید (راه‌یار، تئوری موسیقی، آرتیست‌یار).
- 🎓 دوره های من: دوره‌هایی که کاربر قبلاً خریده و لایسنس/دسترسی آن‌ها.
- 🎼 کلاس آنلاین: کلاس‌های خصوصی زنده (تنظیم، میکس، مسترینگ، تئوری و ...)، رزرو نوبت و اقساط.
- 📝 تکالیف: تکالیف تعیین‌شده توسط مدرس و ارسال پاسخ.
- 📈 پیشرفت من: وضعیت جلسات حاضر/غایب و پیشرفت هر دوره آنلاین.
- 👤 پروفایل: مشخصات، تاریخ عضویت، خریدها.
- 🎁 دعوت از دوستان: لینک دعوت اختصاصی و کد تخفیف پاداش.
- 🆘 پشتیبانی: ثبت تیکت برای مدیریت؛ تنها راه رسمی طرح مشکل یا پیگیری پرداخت.

فرایند خرید دوره دیجیتال: انتخاب دوره از «📚 دوره ها» -> مشاهده جزئیات و قیمت
-> دکمه پرداخت -> مشاهده شماره کارت -> آپلود رسید پرداخت -> تأیید توسط مدیر
-> ارسال خودکار لایسنس (SpotPlayer) یا لینک دعوت کانال تلگرام (آرتیست‌یار).
هیچ دسترسی‌ای قبل از تأیید دستی مدیر فعال نمی‌شود.
""".strip()

SYSTEM_PROMPT_FA = """
تو دستیار راهنمای ربات تلگرامی «آکادمی راه‌یار» هستی. فقط به زبان فارسی و
فقط درباره‌ی استفاده از همین ربات، دوره‌ها و کلاس‌های آنلاینِ زیر پاسخ بده.

قوانین سخت‌گیرانه:
- هرگز شماره کارت، اطلاعات پرداخت یا اطلاعات محرمانه را ننویس؛ همیشه کاربر را
  به همان مسیر داخل ربات (دکمه‌های منو) ارجاع بده.
- هرگز ادعا نکن پرداختی را تأیید/رد کرده‌ای یا لایسنسی صادر کرده‌ای؛ این کار
  فقط با تأیید دستی مدیر انجام می‌شود.
- اگر قیمت یا نام دوره‌ای را نمی‌دانی، آن را حدس نزن؛ فقط از لیست «دوره‌های
  فعال فعلی» که در ادامه داده شده استفاده کن.
- اگر سؤال به مسائل مالی حساس، شکایت، یا مشکلی نیاز به بررسی انسانی دارد،
  کاربر را به «🆘 پشتیبانی» ارجاع بده، نه اینکه خودت قول حل مشکل را بدهی.
- هرگز دستورات مدیریتی/فنی/ادمین را توضیح نده؛ آن بخش فقط برای مالک ربات است.
- پاسخ کوتاه، دوستانه و راهگشا بده؛ از دکمه‌های واقعی منو نام ببر.
"""


class ChatAssistantError(RuntimeError):
    pass


class ChatAssistantService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.course_service = CourseService()
        self.online_course_service = OnlineCourseService()
        # Per-process, per-user sliding window of recent message
        # timestamps. A single bot instance is the deployment model
        # here (see docs/DEPLOYMENT), so in-memory is sufficient and
        # avoids adding a hard Redis dependency for this feature alone.
        self._recent_messages: dict[str, deque[float]] = defaultdict(deque)

    def _check_enabled(self) -> None:
        if not self.settings.CHAT_ASSISTANT_ENABLED:
            raise ChatAssistantError("Chat assistant is disabled in configuration.")
        if not self.settings.CHAT_ASSISTANT_API_KEY:
            raise ChatAssistantError("CHAT_ASSISTANT_API_KEY is not configured.")

    def _check_rate_limit(self, telegram_id: str) -> None:
        limit = self.settings.CHAT_ASSISTANT_MAX_MESSAGES_PER_HOUR
        if limit <= 0:
            return
        now = time.time()
        window = self._recent_messages[telegram_id]
        while window and now - window[0] > 3600:
            window.popleft()
        if len(window) >= limit:
            raise ChatAssistantError(
                "تعداد پیام‌های شما به دستیار در این ساعت به حد مجاز رسیده است. "
                "لطفاً کمی بعد دوباره تلاش کنید یا از «🆘 پشتیبانی» استفاده کنید."
            )
        window.append(now)

    def _catalog_context(self, db: Session) -> str:
        lines: list[str] = ["دوره‌های دیجیتال فعال فعلی:"]
        courses = self.course_service.get_courses(db)
        if not courses:
            lines.append("- در حال حاضر دوره دیجیتالی فعال نیست.")
        for course in courses:
            price = f"{course.price:,} تومان" if course.price else "رایگان"
            delivery = (
                "دیجیتال از طریق SpotPlayer"
                if course.delivery_type == ProductDeliveryType.SPOTPLAYER
                else "کانال تلگرام (آرتیست‌یار)"
            )
            lines.append(f"- {course.title} | {price} | تحویل: {delivery}")

        lines.append("\nکلاس‌های آنلاین فعال فعلی:")
        online_courses = self.online_course_service.get_active_courses(db)
        if not online_courses:
            lines.append("- در حال حاضر کلاس آنلاین فعالی تعریف نشده است.")
        for oc in online_courses:
            monthly = f"{oc.monthly_price:,} تومان" if oc.monthly_price else "-"
            term = f"{oc.term_price:,} تومان" if oc.term_price else "-"
            lines.append(
                f"- {oc.name} | ماهانه: {monthly} ({oc.monthly_sessions} جلسه) "
                f"| ترمی: {term} ({oc.term_sessions} جلسه)"
            )
        return "\n".join(lines)

    def _request_model(self, messages: list[dict]) -> str:
        url = self.settings.CHAT_ASSISTANT_BASE_URL.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.CHAT_ASSISTANT_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.CHAT_ASSISTANT_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.settings.CHAT_ASSISTANT_TIMEOUT_SECONDS
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ChatAssistantError(f"Chat assistant provider request failed: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ChatAssistantError("Chat assistant provider returned an unexpected response.") from exc

    def answer(self, db: Session, telegram_id: str, user_message: str) -> str:
        """Answer a free-text student question. Raises ChatAssistantError
        (disabled, misconfigured, rate-limited, or provider failure) -
        callers must catch this and show a friendly fallback; never let
        it propagate as an unhandled exception to the Telegram layer."""
        self._check_enabled()

        text = (user_message or "").strip()
        if not text:
            raise ChatAssistantError("empty_message")
        if len(text) > MAX_USER_MESSAGE_CHARS:
            text = text[:MAX_USER_MESSAGE_CHARS]

        self._check_rate_limit(telegram_id)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_FA},
            {"role": "system", "content": BOT_GUIDE_FA},
            {"role": "system", "content": self._catalog_context(db)},
            {"role": "user", "content": text},
        ]
        reply = self._request_model(messages)
        return reply[:MAX_REPLY_CHARS]
