title: تجربه پنل ادمین تلگرام
description: منوی مالک — سریع، امن، بدون نیاز به دانش برنامه‌نویسی
tools: read_file, list_tree
tags: design, ux

ADMIN PANEL UX SKILL:

Owner is not a programmer. Every admin screen must be:
- Scannable in 3 seconds
- Safe (confirm destructive actions)
- Reversible navigation (Back always)

Information density:
- Lists: show id + key field + status emoji; details on drill-down
- Avoid dumping full DB rows into one message
- Paginate mentally: if >8 items, prefer short list + «مشاهده بیشتر» patterns already in code

Priority surfaces:
- Pending payments / reservations first (money & schedule)
- Installments overdue
- Support tickets open
- Broadcast last (high impact — require confirm)

Language:
- «تایید»، «رد»، «پرداخت‌شده»، «در انتظار» — same glossary everywhere
- Never expose internal enum names without Persian label

AI Developer Agent submenu:
- Separate consult modes from write modes visually
- Remind that merge to main is manual

Security UX:
- Unauthorized taps → short alert, no menu leakage
- No hidden «secret» admin entry that replaces OWNER_ID checks
