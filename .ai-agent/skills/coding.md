# RahYar AI Skill: Coding

Use this workflow for every development task:

1. Understand the request and identify affected modules.
2. Read project context and existing patterns before changing code.
3. Keep Telegram handlers thin; business rules belong in services.
4. Use repositories for persistence and Alembic for schema changes.
5. Add or update tests for every behavior change.
6. Preserve existing functionality and Persian UX.
7. Keep changes small and reviewable.
8. Never rewrite an applied migration; add a new migration.
9. Run `python -m compileall -q src tests` and `pytest` before PR creation.
10. Summarize files, tests, risks, and rollback considerations in the PR.
