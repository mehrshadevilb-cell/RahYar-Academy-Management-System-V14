# Merge history (2026-09-14)

## Merged

1. PR #4 — AI agent hardening
2. PR #5 — Support (`0004`)
3. PR #12 — Assignments (`0005`) — replaced conflicted #6
4. Progress + class reminders + docs (`0006`) — this integration branch

## Closed without merge

- #2 toy AI stubs
- #3 superseded audit
- #6 old assignments branch
- #7 quizzes (deferred)
- #8 old progress branch (superseded)
- #9 exams (deferred)
- #10 old class-reminders branch (superseded)
- #11 old docs branch (superseded)

## Deploy after this merge

```bash
alembic upgrade head
PYTHONPATH=. pytest -q
```
