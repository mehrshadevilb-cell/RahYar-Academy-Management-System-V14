# RahYar AI Skill: Telegram UI

Use this skill whenever changing the Telegram bot UI, especially the owner/admin AI panel.

## Goal
Make the bot feel polished, clear, fast, and professional while preserving RahYar's Persian-first UX.

## UI principles
1. Prefer compact, scannable Telegram messages over walls of text.
2. Use consistent sections, icons, separators, and status labels.
3. Keep primary actions visible as inline keyboard buttons; avoid requiring slash commands when a button can do the job.
4. Group actions by intent: Assistant, Audit, Debug, Fix, Feature, API Test, Security, Task Status, Stop.
5. Use clear Persian labels. Keep technical identifiers such as model names, branch names, file paths, and test commands in monospace/backticks.
6. Show state explicitly: 🟢 آماده, 🟡 در حال پردازش, 🔴 خطا, ⚪ غیرفعال.
7. Never display API keys, Authorization headers, secrets, .env contents, raw provider responses, or sensitive environment values.
8. Do not expose internal stack traces to Telegram; provide a short Persian explanation and a safe next step.
9. Long-running operations should show one concise progress message and one final result message; do not spam progress updates.
10. Destructive or high-impact actions must be owner-gated and confirmable.

## AI panel layout
Use a dashboard-style home message with:
- AI connection status
- model status without exposing secrets
- repository/agent status
- security status
- primary action buttons
- current task state when applicable

Recommended primary buttons:
- 🤖 دستیار
- 🔍 بررسی کد
- 🐞 دیباگ
- 🛠 رفع باگ
- ✨ قابلیت جدید
- 🧪 تست API
- 🔐 امنیت
- 📋 وضعیت کار
- 🛑 توقف

## Interaction rules
- After an action is selected, explain exactly what input is expected.
- Validate and bound user text before sending it to the AI provider.
- Preserve the current FSM/state flow and never trust callback data as authorization.
- Owner authorization must be checked server-side for every sensitive callback/message handler.
- After completion, summarize: result, changed files, tests, branch/PR status, and any risk requiring owner review.
- If a task is rejected or blocked, explain why in Persian and offer the safest available action.

## Visual consistency
- Use the same emoji for the same concept throughout the bot.
- Avoid excessive emoji; use them as visual anchors, not decoration.
- Prefer short button labels that fit one or two lines.
- Keep button ordering stable so repeated use becomes muscle memory.
- Preserve existing bot functionality while improving presentation.

## Quality gate
Every UI change should be checked for:
- owner authorization
- callback/state correctness
- graceful error handling
- mobile Telegram readability
- Persian copy quality
- no secret leakage
- regression tests where behavior changes
