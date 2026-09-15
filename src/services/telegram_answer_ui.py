"""Presentation helpers for clean, compact Telegram assistant answers."""
from __future__ import annotations

import html
import re


def format_assistant_answer(text: str) -> str:
    """Render plain/markdown-ish model output as safe, polished Telegram HTML."""
    value = (text or "").strip()
    if not value:
        return "🤖 <b>راه‌یار</b>\n\nجوابی پیدا نشد."

    # Escape first: model output must never be able to inject Telegram HTML.
    value = html.escape(value, quote=False)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", value, flags=re.MULTILINE)
    value = re.sub(r"^[*-]\s+", "• ", value, flags=re.MULTILINE)
    value = re.sub(r"\n{3,}", "\n\n", value)

    lines = value.splitlines()
    rendered: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            rendered.append("")
            continue
        if stripped.startswith("🔎 منابع"):
            rendered.append("<b>🔎 منابع</b>")
        elif stripped.startswith("💡") or stripped.startswith("⚠️"):
            rendered.append(f"<b>{stripped[:2]}</b>{stripped[2:]}")
        else:
            rendered.append(line)

    body = "\n".join(rendered).strip()
    return f"🤖 <b>راه‌یار</b>\n\n{body}"
