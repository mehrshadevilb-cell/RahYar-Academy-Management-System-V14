title: استاندارد UX تلگرام راه‌یار
description: قواعد متن و کیبورد برای تجربهٔ یکدست فارسی
tools: read_file, list_tree
tags: design, ux

When polishing Telegram UX for RahYar:
- Keep messages short; one idea per message when possible.
- Use consistent emoji anchors already common in the bot (✅ ❌ ⬅️ 🧠 💳 📅 ⏰ 🎼).
- Admin screens must remain owner-only; never weaken OWNER_ID checks.
- Prefer edit_text over sending new messages for menu navigation.
- Always offer «⬅️ بازگشت» to admin_home or the parent menu.
- Confirmation required before destructive actions (delete, broadcast, reject payment).
- Error copy must tell the owner what to do next in plain Persian.
- Student-facing flows must never show internal enum names or stack traces.
- Match existing keyboard module patterns under src/bot/keyboards/.
