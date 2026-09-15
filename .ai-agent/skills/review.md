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
