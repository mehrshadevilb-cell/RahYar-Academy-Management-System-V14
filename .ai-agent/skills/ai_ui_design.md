# RahYar AI Skill: AI Panel Design

Apply this skill specifically to the AI Developer section inside the Telegram bot.

## Target experience
The AI panel should feel like a small professional control center, not a raw developer console.

### Home card
Use a compact dashboard containing:
- `🤖 RahYar AI Developer`
- connection state
- active model state
- repository state
- security state
- current task, if any

Example structure:
`🤖 RahYar AI Developer`
`━━━━━━━━━━━━━━━━`
`🟢 API: متصل`
`🧠 Model: آماده`
`📂 Repo: متصل`
`🔐 Security: فعال`

Then show the primary actions as an inline keyboard.

## Action hierarchy
First row: Assistant / Audit
Second row: Debug / Fix
Third row: Feature / Test API
Fourth row: Security / Task Status
Final row: Stop

Adapt the exact keyboard to the existing project patterns instead of blindly replacing them.

## API status
The UI may say whether the provider is configured/reachable, but must never reveal the API key, bearer token, complete authorization header, or secret environment values. A provider URL should be omitted or safely summarized if it could disclose sensitive infrastructure.

## Task feedback
For a running task, use concise status updates such as:
- `🟡 در حال تحلیل...`
- `🔎 بررسی فایل‌های مرتبط...`
- `🧪 اجرای تست‌ها...`
- `✅ آماده بررسی`

At completion, show:
- outcome
- files changed
- tests
- branch
- PR/review state
- warnings/risks

## Error UX
Never send raw exceptions or stack traces. Convert known failures into short Persian messages with an actionable next step. Keep detailed diagnostics in safe server logs only, without secrets.

## Design constraints
- Persian-first copy
- mobile-first Telegram readability
- stable button positions
- minimal message spam
- owner-only sensitive operations
- no automatic merge/deploy
- preserve existing behavior
