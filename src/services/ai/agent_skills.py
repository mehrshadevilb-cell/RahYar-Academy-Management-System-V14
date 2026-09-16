"""RahYar AI Agent skill pack — injected into every agent prompt.

These skills train the agent to behave as a senior engineer for this codebase
without inventing APIs, tables, or external behavior.
"""

RAHYAR_AGENT_SKILLS = """
RAHYAR AGENT SKILLS (must follow):

1) Architecture
- Thin Telegram handlers → services → repositories → SQLAlchemy models.
- Never put business rules in handlers.
- Prefer smallest safe change; do not rewrite working modules.

2) Stack
- Python 3.13+, Aiogram 3, SQLAlchemy 2, Alembic, Redis, Pydantic v2, Docker.
- User-facing strings Persian; code English.

3) Payments
- Never mark paid without owner verification workflow.
- Card-to-card: pending → approved/rejected only by admin.
- Entitlements only after approved payment.

4) Online class
- Cancelled reservations must not consume sessions when rules say so.
- Timezone: Asia/Tehran for scheduling.

5) AI routing
- Use the shared provider router; never hardcode a single dead model.
- On model failure, failover is automatic — do not treat one HTTP 404 as total agent failure when another model can answer.

6) Security
- No secrets in commits, logs, or Telegram replies.
- Admin gates via is_admin_user only (OWNER_ID + ADMIN_IDS + ADMIN_USERNAMES).

7) Output quality
- Evidence-based: cite paths/symbols that exist in the inventory.
- Separate CONFIRMED vs NEEDS-VERIFICATION.
- Prefer runnable patches over vague advice.
- Keep answers concise; for write tasks produce complete file contents when required.

8) Speed
- Prefer surgical edits.
- Avoid unnecessary full-repo rewrites.
- For analysis, rank P0/P1 first.

9) Tests
- Critical business rules should be testable without Telegram.
- After code changes, compile + pytest gate before commit/PR.

10) Delivery modes
- SpotPlayer vs ArtistYar Telegram channels are separate; do not mix.
""".strip()
