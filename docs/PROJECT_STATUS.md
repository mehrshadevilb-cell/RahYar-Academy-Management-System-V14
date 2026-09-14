# RahYar Academy Management System

## Status

**Core LMS / CRM feature set is on `main`.**

Quizzes and formal exams were deferred by owner request.

## On `main`

- Telegram bot with role-aware menu and owner admin panel
- Digital products + card-to-card payment + approval gate
- SpotPlayer licenses + ArtistYar invite links (with retry)
- Online class enrollment, reservation, attendance
- Monthly installments + installment reminders (7/3/1/due + overdue)
- **Confirmed class session reminders** (1 day before + same day)
- Discount codes, referrals, broadcast, CSV reports, AdminLog
- Support tickets
- Homework assignments (create / submit / review)
- Student progress dashboard
- AI Developer Agent (hardened; disabled by default)
- Jalali calendar reservation picker
- Alembic migrations through **`0006`**
- CI pytest workflow

## Migrations

| Rev | Feature |
|-----|---------|
| 0004 | Support tickets |
| 0005 | Assignments |
| 0006 | Reservation reminder flags |

```bash
alembic upgrade head
```

## Deferred

- Practice quizzes
- Formal exams
- Live Telegram e2e tests (still manual)

## Run checks

```bash
PYTHONPATH=. pytest -q
python -m compileall -q src tests
```

## Owner

RahYar Academy (`OWNER_ID` in `.env`)
