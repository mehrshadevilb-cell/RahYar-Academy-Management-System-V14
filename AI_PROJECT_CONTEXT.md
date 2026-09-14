# RahYar Academy — AI Project Context

## Mission
RahYar Academy is a Telegram-first LMS/CRM for the academy. The production system must prioritize data integrity, payment correctness, Telegram access control, and safe deployments.

## Stack
- Python 3.13
- aiogram 3
- SQLAlchemy 2
- PostgreSQL in production; SQLite is development-only
- Alembic migrations
- Redis
- FastAPI health endpoints
- Docker / Docker Compose
- pytest + GitHub Actions

## Architecture
`src/bot/handlers` -> `src/services` -> `src/database/repositories` -> `src/database/models`.
Integrations live under `src/integrations`. Shared configuration, security, logging and utilities live under `src/core`.

The production AI Developer Agent entrypoint is `src/services/ai_agent_service.py` + Telegram handlers in `src/bot/handlers/admin_ai.py`.
Do not introduce a second parallel agent runtime under `src/ai_agent/`.

## Non-negotiable rules
1. Never expose or hardcode secrets.
2. Never edit `.env` through the AI agent.
3. Never write directly to production databases from the AI agent.
4. Database schema changes require an Alembic migration.
5. Never rewrite an already-applied migration; add a new migration.
6. Never deploy or merge to `main` without explicit owner approval.
7. AI changes must be isolated on an `ai/*` branch.
8. Run compile checks and tests before considering a change complete.
9. Prefer PostgreSQL integration tests for database behavior that can differ from SQLite.
10. Preserve Persian user-facing text and RTL-friendly Telegram UX.
11. Keep business rules in services, not handlers.
12. Do not silently remove existing business functionality while refactoring.

## Definition of Done
- Change has a clear reason and scope.
- Tests are added/updated for behavior changes.
- `python -m compileall -q src tests` passes.
- `pytest -q` passes.
- Migration upgrade/downgrade is reviewed when schema changes exist.
- Docker build/startup paths remain consistent.
- Security-sensitive changes receive owner review.

## Known audit findings (updated 2026-09-14)
- Resolved on `ai/agent-hardening`: Docker healthcheck for bot service; `pyproject.toml` dependency list aligned with runtime stack; CI already runs compileall + pytest.
- Remaining: live Telegram/API end-to-end coverage is still missing (unit/business-rule suite only).
- Remaining optional: AdminLog rows for AI agent runs.

## AI agent goal
The AI Developer Agent may inspect code, diagnose failures, propose fixes/features, create isolated branches, edit source/tests/migrations, run checks, and prepare a reviewable change. Deployment remains an owner-approved operation.

See `.ai-agent/policy.md` for the full security policy.
