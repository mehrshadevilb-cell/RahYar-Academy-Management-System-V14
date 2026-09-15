"""Presentation helpers for clean, compact Telegram assistant answers."""
from __future__ import annotations

import html
import re


def format_assistant_answer(text: str) -> str:
    """Render model output as safe, polished, compact Telegram HTML."""
    value = (text or "").strip()
    if not value:
        return "🤖 <b>راه‌یار</b>\n\nجوابی پیدا نشد."

    # Escape first: model output must never be able to inject Telegram HTML.
    value = html.escape(value, quote=False)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", value, flags=re.MULTILINE)
    value = re.sub(r"^[*-]\s+", "• ", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*[-=]{3,}\s*$", "", value, flags=re.MULTILINE)
    value = re.sub(r"\n{3,}", "\n\n", value)

    lines = value.splitlines()
    rendered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if rendered and rendered[-1] != "":
                rendered.append("")
            continue

        # Keep common answer sections visually distinct without making the UI noisy.
        section = re.match(r"^(?:🎯\s*)?(?:جواب|پیشنهاد|انتخاب|مقایسه)\s*:?[ ]*(.*)$", stripped, re.I)
        if section:
            suffix = f" — {section.group(1)}" if section.group(1) else ""
            rendered.append(f"<b>🎯 {stripped.split(':', 1)[0].replace('🎯', '').strip()}</b>{suffix}")
        elif stripped.startswith("🔎 منابع") or stripped.startswith("📚 منابع"):
            rendered.append("<b>🔎 منابع</b>")
        elif stripped.startswith("💡") or stripped.startswith("⚠️") or stripped.startswith("⚙️"):
            rendered.append(f"<b>{stripped[:2]}</b>{stripped[2:]}")
        elif stripped.startswith(("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣")):
            rendered.append(stripped)
        else:
            rendered.append(line)

    body = "\n".join(rendered).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    return f"🤖 <b>راه‌یار</b>\n\n{body}"
