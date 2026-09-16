# RahYar AI Skill: Debug & Fast Fix

Use this skill for bugs, stack traces, production incidents, and automated fix tasks.

## Speed rules
1. Prefer the smallest reproducible path — do not scan the whole repository.
2. Rank hypotheses by evidence from the stack trace and exact symbols.
3. Change only the files required to fix the root cause.
4. Prefer a targeted pytest over a full-suite loop when the failing area is clear.
5. Stop after the first correct fix that passes compile + relevant tests.

## Debug workflow
1. Extract: exception type, message, file:line, handler/service names.
2. Reproduce mentally from the stack — do not invent missing frames.
3. Rank 1–3 root-cause hypotheses with confidence.
4. Inspect only the listed paths/symbols.
5. Apply the smallest safe patch.
6. Add or tighten a regression test that would have failed before the fix.
7. Run `python -m compileall -q src tests` and the focused pytest path.
8. Summarize cause, fix, tests, and residual risk for the owner.

## Auto-fix constraints (critical)
- Write only on `ai/*` branches.
- Never merge to `main` and never deploy.
- Never disable or weaken tests to make CI green.
- Never touch `.env`, tokens, payment approval rules, or admin authorization.
- If evidence is insufficient, stop and report what log/path is needed.
- Rate-limit automatic retries; do not thrash the same error fingerprint.

## Output contract for fix tasks
- Root cause (one sentence)
- Files changed
- Regression test
- Residual risk / rollback
