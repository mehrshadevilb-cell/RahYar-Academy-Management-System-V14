"""Presentation helpers for clean, compact Telegram assistant answers."""
from __future__ import annotations

import html
import re

MAX_TELEGRAM_ANSWER_CHARS = 3900


def _normalize_model_markup(value: str) -> str:
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"__(.+?)__", r"<b>\1</b>", value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", value, flags=re.MULTILINE)
    value = re.sub(r"^[*-]\s+", "• ", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*[-=]{3,}\s*$", "", value, flags=re.MULTILINE)
    return value


def _section_title(line: str) -> str | None:
    clean = line.strip()
    clean = re.sub(r"^<b>(.+?)</b>$", r"\1", clean)
    clean = re.sub(r"^[🎯📌💡🔎📚⚙️🧠]\s*", "", clean)
    match = re.match(r"^(جواب|پاسخ|نتیجه|مراحل|نکات|پیشنهاد|انتخاب|مقایسه|هشدار|منابع)\s*:?(.*)$", clean, re.I)
    if not match:
        return None
    title = match.group(1)
    emoji = {
        "جواب": "🎯",
        "پاسخ": "🎯",
        "نتیجه": "🎯",
        "مراحل": "🛠️",
        "نکات": "💡",
        "پیشنهاد": "💡",
        "انتخاب": "🎛️",
        "مقایسه": "⚖️",
        "هشدار": "⚠️",
        "منابع": "🔎",
    }.get(title, "📌")
    return f"<b>{emoji} {title}</b>"


def format_assistant_answer(text: str) -> str:
    """Render model output as safe, polished, compact Telegram HTML."""
    value = (text or "").strip()
    if not value:
        return "🤖 <b>راه‌یار</b>\n\nجوابی پیدا نشد."

    # Escape first: model output must never be able to inject Telegram HTML.
    value = html.escape(value, quote=False)
    value = _normalize_model_markup(value)
    value = re.sub(r"\n{3,}", "\n\n", value)

    lines = value.splitlines()
    rendered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if rendered and rendered[-1] != "":
                rendered.append("")
            continue

        section = _section_title(stripped)
        if section:
            rendered.append(section)
        elif stripped.startswith(("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣")):
            rendered.append(stripped)
        elif stripped.startswith("🔎 منابع") or stripped.startswith("📚 منابع"):
            rendered.append("<b>🔎 منابع</b>")
        elif stripped.startswith(("💡", "⚠️", "⚙️")):
            rendered.append(f"<b>{stripped[:2]}</b>{stripped[2:]}")
        else:
            rendered.append(line)

    body = re.sub(r"\n{3,}", "\n\n", "\n".join(rendered)).strip()
    # Keep a small safety margin below Telegram's 4096-character message limit.
    if len(body) > MAX_TELEGRAM_ANSWER_CHARS:
        body = body[:MAX_TELEGRAM_ANSWER_CHARS - 1].rsplit(" ", 1)[0].rstrip() + "…"
    return f"🤖 <b>راه‌یار</b>\n\n{body}"
