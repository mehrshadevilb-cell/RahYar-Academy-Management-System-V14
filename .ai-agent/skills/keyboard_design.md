title: طراحی کیبورد اینلاین
description: چیدمان دکمه‌ها، برچسب‌ها، بازگشت و تأیید
tools: read_file, list_tree
tags: design, ux

KEYBOARD DESIGN SKILL (aiogram InlineKeyboard):

1) Layout rules:
   - Max 2 primary actions per row when labels are long
   - 3 narrow actions per row only if labels ≤ ~10 chars
   - Destructive action never sits alone next to Confirm without separation
   - Always put «⬅️ بازگشت» on its own bottom row (or with 🛑 توقف for AI flows)

2) Label language (Persian):
   - Verb-first, short: «تایید پرداخت»، «رد درخواست»، «مشاهده جزئیات»
   - Avoid technical jargon on buttons (no “callback”, “FSM”, “PR”)
   - Same action = same label across the whole bot

3) Callback data:
   - Keep existing prefixes (admin_, ai_, res_, …); do not invent parallel schemes
   - Never rely on obscurity for authorization — OWNER_ID / role checks stay in handlers

4) Navigation:
   - Every multi-step flow needs Back and a way to Cancel/Exit
   - Prefer edit_text + new keyboard over flooding new messages
   - After success, return user to a stable menu (admin_home or parent)

5) Confirmation pattern for dangerous ops:
   - Step 1: explain consequence in Persian
   - Step 2: two buttons «✅ بله، انجام بده» / «❌ انصراف»
   - Only then execute

6) Consistency:
   - Reuse modules under src/bot/keyboards/
   - Mirror patterns from admin_menu_keyboard and admin_ai_keyboard
