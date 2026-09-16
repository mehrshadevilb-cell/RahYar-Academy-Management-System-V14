# Skill: Telegram UI (RahYar)

## Principles
- Persian labels on all user-facing buttons
- One clear next action; always provide بازگشت where nested
- Dangerous actions need confirmation
- Avoid message spam; edit in place when possible

## Admin menu structure
Keep high-value ops near top: گزارش امروز، وضعیت سیستم، پرداخت، رزرو، کلاس آنلاین.
Do not duplicate stats and dashboard.

## AI panel
See `ai_ui_design.md`. Unified audit + diagnostics.

## Online class flows
Reservation confirm/reject and attendance must match service-layer business rules
(cancelled sessions must not consume remaining sessions incorrectly).
