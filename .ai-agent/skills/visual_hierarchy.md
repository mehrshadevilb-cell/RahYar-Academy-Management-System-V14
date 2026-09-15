title: سلسله‌مراتب بصری پیام
description: ساختار پیام تلگرام — عنوان، بدنه، اقدام، وضعیت
tools: read_file, list_tree
tags: design, ux

VISUAL HIERARCHY SKILL (Telegram messages):

1) Message skeleton (preferred order):
   - Line 1: emoji + short title (what screen is this?)
   - Blank line
   - Body: 2–5 short lines max; facts first, explanation second
   - Status line if needed (✅ / ⏳ / ❌)
   - CTA hint only when user must act next

2) Density:
   - Prefer one idea per message
   - Avoid walls of text (>12 lines) — split or use bullets
   - Numbers and amounts on their own line when important (prices, sessions)

3) Emphasis without markdown spam:
   - Use emoji as section anchors, not decoration on every word
   - Consistent anchors already used in RahYar: ✅ ❌ ⬅️ 🧠 💳 📅 ⏰ 🎼
   - Do not invent a new emoji language per screen

4) Lists:
   - Use • or numbered list for 3+ items
   - Keep each bullet ≤ 1 line when possible

5) Empty / loading / error states:
   - Empty: what is missing + one clear next action
   - Loading: one short “در حال …” message, no spam
   - Error: what failed + what the user can do (retry / back / support)

6) Never change business rules while redesigning hierarchy.
