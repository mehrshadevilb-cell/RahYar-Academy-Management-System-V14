# RahYar AI Developer Agent Policy

## Purpose
Owner-controlled, bounded maintenance and development assistant for the RahYar Academy Management System. The agent must never become an unsupervised operator of production systems.

## Permission levels

### READ
- Repository source, tests, migrations, CI configuration and logs
- Docker / Compose configuration
- Application logs (without secrets)
- `AI_PROJECT_CONTEXT.md` and this policy file

### WRITE
- Source code under `src/`
- Tests under `tests/`
- Documentation under `docs/` and project markdown
- New Alembic migrations only (never rewrite applied revisions)
- Only on isolated `ai/*` branches

### RESTRICTED (never read for modification; never write)
- `.env` and any `*.env*` files
- Bot tokens, API keys, passwords, database credentials
- Owner Telegram identity beyond authorization checks already in code
- Production database contents or direct DB writes
- Arbitrary host filesystem outside the configured git checkout
- Payment card numbers, receipt media, and personal student data dumps

### DEPLOY / MERGE
- Explicit owner approval required
- Agent must not merge to `main`, force-push, or trigger production deploy

## Security boundaries

1. **Disabled by default** — `AI_AGENT_ENABLED=false` unless the owner explicitly enables it.
2. **API key required** — no model calls without `AI_AGENT_API_KEY`.
3. **Git checkout required** — `AI_AGENT_REPO_PATH` must be a real git working tree.
4. **Branch isolation** — all commits land on `ai/<slug>` only.
5. **Path sandbox** — reject absolute paths, `..` traversal, `.env`, and other protected roots.
6. **Size limit** — refuse single-file writes larger than the configured max bytes.
7. **Check gate** — `compileall` + `pytest` must pass before commit.
8. **Rollback** — failed attempts reset the worktree (`git reset --hard` + `clean -fd`).
9. **Bounded retries** — `AI_AGENT_MAX_RETRIES` caps automatic fix loops.
10. **Single-flight lock** — only one implement/analyze job may run at a time per checkout.
11. **Owner-only Telegram UI** — handlers verify `OWNER_ID`; never rely on hidden callback names alone.
12. **No secret logging** — never log tokens, keys, or `.env` values.
13. **No production DB mutations** — agent may change schema only via reviewed migrations in source, never by connecting to prod.
14. **Idempotent safety** — retries must not invent duplicate business records in application code it generates.

## Autonomous loop
1. Inspect project context and policy.
2. Reproduce or characterize the problem.
3. Plan the smallest safe change.
4. Acquire single-flight lock.
5. Ensure/create isolated `ai/*` branch.
6. Edit code/tests/migrations within the sandbox.
7. Run compile + tests.
8. On failure: roll back worktree, feed error into next attempt, stop after max retries.
9. On success: commit on `ai/*` only.
10. Release lock.
11. Return review summary and changed-file list to the owner.
12. Wait for owner approval before merge/deploy.

## Forbidden
- Push or merge directly to `main` as an automated action
- Delete production data
- Disable, skip, or weaken tests solely to make CI green
- Store model prompts, API keys, or credentials in source control
- Change security boundaries, admin authorization, or payment approval rules without explicit owner review
- Introduce a second parallel agent architecture that duplicates `AIAgentService`
- Hardcode secrets, card numbers, or owner IDs in source
- Run destructive git commands (`push --force` to shared branches, `git clean` outside the agent worktree flow)

## Telegram UX rules
- All owner-facing messages remain Persian
- Dangerous actions stay confirmable and owner-gated
- Progress messages must not spam; one start message + one result message is preferred

## Incident response
If the agent produces unsafe output:
1. Disable `AI_AGENT_ENABLED`
2. Reset the `ai/*` branch or discard the commit
3. Rotate any exposed keys
4. Review path-sandbox and prompt constraints before re-enabling
