# RahYar AI Developer Agent Policy

## Permission levels

### READ
Repository source, tests, migrations, CI logs, Docker configuration and application logs.

### WRITE
Source code, tests, documentation and new Alembic migrations on `ai/*` branches.

### RESTRICTED
`.env`, tokens, passwords, production database credentials, owner identity, Telegram credentials and arbitrary host filesystem access.

### DEPLOY
Explicit owner approval required.

## Autonomous loop
1. Inspect project context.
2. Reproduce or characterize the problem.
3. Plan the smallest safe change.
4. Create an isolated `ai/*` branch.
5. Edit code/tests/migrations.
6. Run compile + tests.
7. If tests fail, inspect failures and retry with a bounded retry count.
8. Produce a review summary and changed-file list.
9. Wait for owner approval before merge/deploy.

## Forbidden
- Push directly to `main` as an automated repair action.
- Delete production data.
- Disable tests merely to make CI green.
- Store model prompts, API keys or credentials in source control.
- Change security boundaries without explicit review.
