"""Learn lightweight personality / learning-style signals from group messages.

Design goals:
- Recognize returning members and adapt assistant tone
- Help teachers understand engagement style
- Do NOT archive full conversations or private content
"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from src.ai.provider_router import AIProviderError, AIProviderRouter
from src.core.config.settings import get_settings
from src.database.models.member_personality import MemberPersonalityProfile
from src.database.repositories.telegram_repository import TelegramRepository

_INTEREST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mix": ("میکس", "mix", "eq", "کمپرسور", "compressor", "reverb", "دی‌اس"),
    "master": ("مستر", "master", "loudness", "limiter"),
    "daw": ("cubase", "ableton", "fl studio", "studio one", "logic", "daw"),
    "plugin": ("پلاگین", "plugin", "waves", "arturia", "izotope"),
    "theory": ("تئوری", "گام", "آکورد", "هارمونی", "ریتم", "theory"),
    "recording": ("ضبط", "میکروفون", "record", "vocal", "وکال"),
    "arrange": ("تنظیم", "arrangement", "آهنگسازی"),
}

_POSITIVE = ("مرسی", "ممنون", "عالی", "دمت", "👏", "🙏", "❤️", "خوبه", "عالیه", "thanks")
_NEGATIVE = ("احمق", "چرت", "آشغال", "بی‌خود", "لعنت", "fuck", "shit")
_HELP = ("اینطوری", "باید", "سعی کن", "پیشنهاد", "راهش اینه", "try", "you can", "می‌تونی")
_QUESTION_MARKERS = ("؟", "?", "چطور", "چگونه", "چرا", "آیا", "میشه", "چیکار")

_SUMMARY_EVERY_N = 12
_MAX_SIGNAL_LINES = 15
_MAX_SIGNAL_CHARS = 1200


class MemberPersonalityService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.telegram_repo = TelegramRepository()
        self._router: AIProviderRouter | None = None

    def _router_lazy(self) -> AIProviderRouter:
        if self._router is None:
            self._router = AIProviderRouter()
        return self._router

    def get_by_telegram_id(self, db: Session, telegram_id: str) -> MemberPersonalityProfile | None:
        return (
            db.query(MemberPersonalityProfile)
            .filter(MemberPersonalityProfile.telegram_id == str(telegram_id))
            .one_or_none()
        )

    def context_for_assistant(self, db: Session, telegram_id: str) -> str:
        """Short block injected into chat assistant system context."""
        profile = self.get_by_telegram_id(db, str(telegram_id))
        if not profile or profile.message_count < 3:
            return ""
        tags = profile.interest_tags or "—"
        summary = (profile.summary_fa or "هنوز خلاصه کافی نیست.").strip()
        return (
            "شناخت تعاملی این کاربر از فعالیت گروهی (خلاصه؛ داده خصوصی نیست):\n"
            f"- پیام‌ها: {profile.message_count} | سؤال‌ها: {profile.question_count}\n"
            f"- کنجکاوی: {profile.curiosity_score:.2f} | کمک‌رسانی: {profile.helpfulness_score:.2f} | ادب: {profile.politeness_score:.2f}\n"
            f"- علاقه‌ها: {tags}\n"
            f"- خلاصه: {summary}\n"
            "لحن پاسخ را با این سبک یادگیری هماهنگ کن؛ داده حساس یا قضاوت توهین‌آمیز نساز."
        )

    def observe_message(
        self,
        db: Session,
        *,
        telegram_id: str,
        text: str,
        display_name: str | None = None,
    ) -> MemberPersonalityProfile | None:
        if not getattr(self.settings, "GROUP_LEARNING_ENABLED", True):
            return None
        body = (text or "").strip()
        if not body or body.startswith("/"):
            return None
        if len(body) < 2:
            return None

        tid = str(telegram_id)
        profile = self.get_by_telegram_id(db, tid)
        if profile is None:
            account = self.telegram_repo.get_by_telegram_id(db, tid)
            profile = MemberPersonalityProfile(
                telegram_id=tid,
                user_id=account.user_id if account else None,
                display_name=(display_name or "")[:120] or None,
            )
            db.add(profile)

        if display_name:
            profile.display_name = display_name[:120]
        if profile.user_id is None:
            account = self.telegram_repo.get_by_telegram_id(db, tid)
            if account:
                profile.user_id = account.user_id

        signals = self._analyze(body)
        profile.message_count = int(profile.message_count or 0) + 1
        if signals["is_question"]:
            profile.question_count = int(profile.question_count or 0) + 1
        if signals["is_help"]:
            profile.help_count = int(profile.help_count or 0) + 1
        if signals["is_positive"]:
            profile.positive_count = int(profile.positive_count or 0) + 1
        if signals["is_negative"]:
            profile.negative_count = int(profile.negative_count or 0) + 1

        profile.interest_tags = self._merge_tags(profile.interest_tags, signals["tags"])
        profile.curiosity_score = self._clamp(
            0.7 * float(profile.curiosity_score or 0)
            + 0.3 * (1.0 if signals["is_question"] else 0.15)
        )
        profile.helpfulness_score = self._clamp(
            0.7 * float(profile.helpfulness_score or 0)
            + 0.3 * (1.0 if signals["is_help"] else 0.1)
        )
        polite_delta = 0.7 if signals["is_positive"] else (-0.5 if signals["is_negative"] else 0.05)
        profile.politeness_score = self._clamp(
            0.85 * float(profile.politeness_score if profile.politeness_score is not None else 0.5)
            + 0.15 * (0.5 + polite_delta)
        )
        profile.engagement_score = self._clamp(min(1.0, (profile.message_count or 0) / 40.0))
        profile.last_message_at = datetime.utcnow()
        profile.recent_signals = self._append_signal(profile.recent_signals, signals["snippet"])

        db.commit()
        db.refresh(profile)

        if profile.message_count % _SUMMARY_EVERY_N == 0:
            self._refresh_summary(db, profile)
        return profile

    def format_admin_view(self, profile: MemberPersonalityProfile) -> str:
        tags = profile.interest_tags or "—"
        name = profile.display_name or profile.telegram_id
        return (
            f"🧠 پروفایل تعاملی: {name}\n"
            f"telegram_id: {profile.telegram_id}\n"
            f"پیام‌ها: {profile.message_count} | سؤال: {profile.question_count} | کمک: {profile.help_count}\n"
            f"مثبت/منفی: {profile.positive_count}/{profile.negative_count}\n"
            f"کنجکاوی: {profile.curiosity_score:.2f}\n"
            f"کمک‌رسانی: {profile.helpfulness_score:.2f}\n"
            f"ادب/لحن: {profile.politeness_score:.2f}\n"
            f"درگیری: {profile.engagement_score:.2f}\n"
            f"علاقه‌ها: {tags}\n\n"
            f"خلاصه:\n{profile.summary_fa or 'هنوز به‌اندازه کافی پیام دیده نشده.'}"
        )

    def _analyze(self, text: str) -> dict:
        low = text.casefold()
        tags = [name for name, keys in _INTEREST_KEYWORDS.items() if any(k in low for k in keys)]
        is_question = any(m in text for m in _QUESTION_MARKERS) or text.strip().endswith(("؟", "?"))
        is_help = any(h in low for h in _HELP) and len(text) > 20
        is_positive = any(p in low for p in _POSITIVE)
        is_negative = any(n in low for n in _NEGATIVE)
        snippet = re.sub(r"\s+", " ", text)[:160]
        return {
            "tags": tags,
            "is_question": is_question,
            "is_help": is_help,
            "is_positive": is_positive,
            "is_negative": is_negative,
            "snippet": snippet,
        }

    @staticmethod
    def _merge_tags(existing: str | None, new_tags: list[str]) -> str:
        current = [t for t in (existing or "").split(",") if t.strip()]
        for t in new_tags:
            if t not in current:
                current.append(t)
        return ",".join(current[:20])

    @staticmethod
    def _append_signal(existing: str | None, snippet: str) -> str:
        lines = [ln for ln in (existing or "").split("\n") if ln.strip()]
        lines.append(snippet)
        lines = lines[-_MAX_SIGNAL_LINES:]
        joined = "\n".join(lines)
        return joined[:_MAX_SIGNAL_CHARS]

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _refresh_summary(self, db: Session, profile: MemberPersonalityProfile) -> None:
        """Optional LLM rewrite of the Persian educational summary."""
        signals = profile.recent_signals or ""
        prompt = (
            "بر اساس سیگنال‌های زیر، یک خلاصه کوتاه فارسی (حداکثر ۴ خط) از سبک یادگیری و اخلاق تعاملی "
            "این هنرجو در گروه آموزشی بنویس. قضاوت توهین‌آمیز نکن. حدس پزشکی/روان‌پزشکی نزن. "
            "روی علاقه موسیقی، کنجکاوی، کمک به دیگران و لحن تمرکز کن.\n\n"
            f"تعداد پیام: {profile.message_count}\n"
            f"سؤال: {profile.question_count} | کمک: {profile.help_count}\n"
            f"علاقه: {profile.interest_tags or '—'}\n"
            f"نمونه‌سیگنال‌ها:\n{signals}"
        )
        try:
            data = self._router_lazy().chat(
                [
                    {"role": "system", "content": "تو تحلیل‌گر کوتاه سبک یادگیری برای آکادمی موسیقی هستی."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=220,
                timeout_seconds=25,
            )
            content = str(data["choices"][0]["message"]["content"]).strip()
            if content:
                profile.summary_fa = content[:900]
                profile.last_summary_at = datetime.utcnow()
                db.commit()
        except (AIProviderError, KeyError, IndexError, TypeError, Exception):
            # Heuristic fallback summary — never fail the observe path.
            if not profile.summary_fa:
                tags = profile.interest_tags or "عمومی"
                profile.summary_fa = (
                    f"فعال در گروه با حدود {profile.message_count} پیام. "
                    f"علاقه‌مندی‌ها: {tags}. "
                    f"نسبت سؤال‌محور: {profile.curiosity_score:.0%}، کمک‌رسانی: {profile.helpfulness_score:.0%}."
                )
                profile.last_summary_at = datetime.utcnow()
                db.commit()
