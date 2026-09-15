title: کپی‌رایتینگ فارسی بات
description: لحن حرفه‌ای، واضح، بدون اصطلاح فنی برای صاحب آکادمی و هنرجو
tools: read_file, list_tree
tags: design, ux

PERSIAN COPY SKILL:

Audience:
- Owner/admin: practical, respectful, non-technical
- Student: warm, clear, step-by-step

Tone:
- Professional music academy (RahYar) — not childish, not corporate-cold
- Use «شما» consistently
- Prefer plain verbs: ثبت شد، تایید شد، ارسال کنید، انتخاب کنید

Do:
- One instruction per sentence when guiding a payment or reservation flow
- State amounts with تومان and thousand separators when showing numbers in copy suggestions
- For errors: «متأسفانه …» + reason in plain words + next step

Don't:
- Stack traces, English exception names, or SQL in user-facing text
- Blame the user
- Long formal essays inside Telegram bubbles

Templates:
- Success: «✅ … انجام شد.» + optional one-line next step
- Pending: «⏳ … در انتظار بررسی است.»
- Rejected: «❌ … رد شد.» + short reason if available
- Need input: «لطفاً … را بفرستید.» + example when format matters

When rewriting existing strings, keep meaning identical; only improve clarity and rhythm.
