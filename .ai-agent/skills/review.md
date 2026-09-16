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

Block a change when it weakens security, bypasses tests, writes to `main`, or exposes sensitive configuration.

## Fast review checklist for auto-fix PRs
1. Is the root cause evidenced by a stack path/symbol?
2. Is the diff the smallest safe fix?
3. Does a regression test exist?
4. Are secrets and payment/admin boundaries untouched?
5. Is the branch still `ai/*` only?
