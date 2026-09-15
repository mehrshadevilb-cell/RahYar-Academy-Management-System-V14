# RahYar AI Skill: Review

Review every proposed change for:

- correctness and regressions
- authorization and owner-only boundaries
- secret leakage
- unsafe filesystem or subprocess access
- SQL/query safety
- migration safety
- Telegram UX and Persian copy
- test coverage
- unnecessary dependencies
- operational rollback path
- deterministic diagnostics before and after edits
- `git diff --check`, syntax/import health, and complete pytest verification
- performance regressions: unnecessary network calls, N+1 queries, blocking I/O in async handlers, oversized prompts, and repeated expensive scans

## Evidence-first debugging

1. Reproduce or characterize the failure before proposing a fix.
2. Prefer the deterministic diagnostics engine (`src/services/ai_agent_diagnostics.py`) for cheap objective checks.
3. Separate confirmed failures from hypotheses that need runtime verification.
4. After edits, run the full verification gate and use the actual failure output as the next repair prompt.
5. Never silence, weaken, skip, or rewrite a test just to obtain a green result.

## Security gate

Block a change when it weakens security, bypasses tests, writes to `main`, exposes sensitive configuration, introduces hard-coded credentials, or expands filesystem/network access without an explicit owner-approved requirement.
