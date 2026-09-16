"""Parse owner Persian chat into structured online-enrollment intents.

Deterministic rules (no LLM) so production enrollments stay predictable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


WEEKDAYS = {
    "شنبه": "شنبه",
    "یکشنبه": "یکشنبه",
    "یک شنبه": "یکشنبه",
    "دوشنبه": "دوشنبه",
    "دو شنبه": "دوشنبه",
    "سه‌شنبه": "سه‌شنبه",
    "سه شنبه": "سه‌شنبه",
    "سهشنبه": "سه‌شنبه",
    "چهارشنبه": "چهارشنبه",
    "چهار شنبه": "چهارشنبه",
    "پنجشنبه": "پنجشنبه",
    "پنج شنبه": "پنجشنبه",
    "جمعه": "جمعه",
}

# Longer aliases first when matching.
COURSE_ALIASES: list[tuple[str, tuple[str, ...]]] = [
    (
        "تنظیم / میکس و مسترینگ",
        (
            "تنظیم، میکس و مسترینگ",
            "تنظیم میکس و مسترینگ",
            "تنظیم میکس مسترینگ",
            "میکس و مسترینگ",
            "میکس مستر",
            "تنظیم",
            "arrangement",
            "mixing",
            "mastering",
            "tanzim",
            "mix",
            "master",
        ),
    ),
    ("پیانو", ("پیانو", "piano")),
    ("تئوری موسیقی", ("تئوری موسیقی", "تئوری", "theory")),
    ("هارمونی", ("هارمونی", "harmony")),
    ("گوش‌ورزی", ("گوش‌ورزی", "گوش ورزی", "ear training")),
]


@dataclass
class ChatEnrollmentDraft:
    student_name: str | None = None
    phone: str | None = None
    course_hint: str | None = None
    weekday: str | None = None
    time_from: str | None = None
    time_to: str | None = None
    remaining_sessions: int | None = None
    weeks: int | None = None
    plan: str = "term"  # monthly | term
    raw_text: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.phone and (self.remaining_sessions or self.weeks) and self.course_hint)

    def schedule_note(self) -> str:
        parts: list[str] = []
        if self.weekday:
            parts.append(f"روز: {self.weekday}")
        if self.time_from and self.time_to:
            parts.append(f"ساعت {self.time_from} تا {self.time_to}")
        elif self.time_from:
            parts.append(f"ساعت {self.time_from}")
        if self.weeks:
            parts.append(f"{self.weeks} هفته")
        return " | ".join(parts) if parts else ""


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if digits.startswith("98") and len(digits) >= 12:
        digits = "0" + digits[2:]
    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    if len(digits) == 11 and digits.startswith("09"):
        return digits
    return None


def _extract_phone(text: str) -> str | None:
    # Prefer explicit 09… or +98…
    for match in re.finditer(r"(?:\+?98|0)?9\d{9}", re.sub(r"[\s\-]", "", text)):
        phone = normalize_phone(match.group(0))
        if phone:
            return phone
    # Spaced Iranian numbers: 0912 345 6789
    spaced = re.search(r"0?9(?:[\s\-]?\d){9}", text)
    if spaced:
        return normalize_phone(spaced.group(0))
    return None


def _extract_sessions(text: str) -> tuple[int | None, int | None]:
    remaining = None
    weeks = None
    m = re.search(r"(\d+)\s*جلسه", text)
    if m:
        remaining = int(m.group(1))
    m = re.search(r"(\d+)\s*هفته", text)
    if m:
        weeks = int(m.group(1))
        if remaining is None:
            remaining = weeks  # assume 1 session/week unless said otherwise
    m = re.search(r"(\d+)\s*جلسه\s*(?:دیگر|دیگه|باقی)", text)
    if m:
        remaining = int(m.group(1))
    m = re.search(r"(?:باقی|مانده|مونده)[^0-9]{0,12}(\d+)\s*جلسه", text)
    if m:
        remaining = int(m.group(1))
    return remaining, weeks


def _extract_weekday(text: str) -> str | None:
    # Prefer «هر سه‌شنبه» patterns
    for key, value in sorted(WEEKDAYS.items(), key=lambda kv: -len(kv[0])):
        if key in text:
            return value
    return None


def _extract_time_range(text: str) -> tuple[str | None, str | None]:
    # ساعت 4 تا 6 / 16-18 / 4:00 تا 18:00
    m = re.search(
        r"ساعت\s*(\d{1,2})(?::(\d{2}))?\s*(?:تا|-)\s*(\d{1,2})(?::(\d{2}))?",
        text,
    )
    if m:
        h1, m1, h2, m2 = m.group(1), m.group(2) or "00", m.group(3), m.group(4) or "00"
        return f"{int(h1):02d}:{m1}", f"{int(h2):02d}:{m2}"
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(?:تا|-)\s*(\d{1,2})(?::(\d{2}))?", text)
    if m and "جلسه" not in m.group(0):
        h1, m1, h2, m2 = m.group(1), m.group(2) or "00", m.group(3), m.group(4) or "00"
        # Avoid matching «12 جلسه» style if second number is large sessions already handled
        if int(h1) <= 24 and int(h2) <= 24:
            return f"{int(h1):02d}:{m1}", f"{int(h2):02d}:{m2}"
    return None, None


def _extract_course_hint(text: str) -> str | None:
    lowered = text.casefold()
    for canonical, aliases in COURSE_ALIASES:
        for alias in aliases:
            if alias.casefold() in lowered or alias in text:
                return canonical
    return None


def _extract_name(text: str, phone: str | None) -> str | None:
    cleaned = text
    if phone:
        cleaned = cleaned.replace(phone, " ")
        cleaned = re.sub(r"(?:\+?98|0)?9\d{9}", " ", cleaned)
    # Common prefixes
    cleaned = re.sub(
        r"(ثبت\s*نام|اضافه\s*کن|کلاس|دوره|جلسه|هفته|ساعت|هر|تا|برای|با|شماره|موبایل)",
        " ",
        cleaned,
    )
    for key in WEEKDAYS:
        cleaned = cleaned.replace(key, " ")
    # Keep Persian letters and spaces
    tokens = re.findall(r"[\u0600-\u06FFa-zA-Z]{2,}", cleaned)
    stop = {
        "هنرجو",
        "دانشجو",
        "داره",
        "دارد",
        "دیگه",
        "دیگر",
        "تکمیل",
        "دوره",
        "آنلاین",
        "class",
        "online",
    }
    name_parts = [t for t in tokens if t.casefold() not in stop and t not in WEEKDAYS]
    if not name_parts:
        return None
    # Take first 2-4 tokens as name
    return " ".join(name_parts[:4]).strip() or None


def parse_enrollment_chat(text: str) -> ChatEnrollmentDraft:
    raw = (text or "").strip()
    draft = ChatEnrollmentDraft(raw_text=raw)
    if not raw:
        draft.warnings.append("متن خالی است")
        return draft

    draft.phone = _extract_phone(raw)
    draft.remaining_sessions, draft.weeks = _extract_sessions(raw)
    draft.weekday = _extract_weekday(raw)
    draft.time_from, draft.time_to = _extract_time_range(raw)
    draft.course_hint = _extract_course_hint(raw)
    draft.student_name = _extract_name(raw, draft.phone)

    if "ماهانه" in raw or "ماهیانه" in raw:
        draft.plan = "monthly"
    elif "ترم" in raw or "ترمی" in raw or (draft.remaining_sessions and draft.remaining_sessions >= 8):
        draft.plan = "term"

    if not draft.phone:
        draft.warnings.append("شماره موبایل پیدا نشد")
    if not draft.course_hint:
        draft.warnings.append("نوع کلاس (مثلاً تنظیم/میکس) پیدا نشد")
    if not draft.remaining_sessions and not draft.weeks:
        draft.warnings.append("تعداد جلسه یا هفته پیدا نشد")
    if not draft.student_name:
        draft.warnings.append("نام هنرجو مبهم است")

    return draft
