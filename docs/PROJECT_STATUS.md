# RahYar Academy Management System

## Status

**Core LMS / CRM feature set is implemented** and waiting on owner merge of open PRs.
Production base (`main`) already runs payments, SpotPlayer, ArtistYar, online classes,
installments, discounts, referrals, reports, and the AI agent foundation.

## On `main` today

- Telegram bot with role-aware menu and owner admin panel
- Digital products + card-to-card payment + approval gate
- SpotPlayer licenses + ArtistYar invite links (with retry)
- Online class enrollment, reservation, attendance (session accounting rules)
- Monthly installments + background reminder scheduler (7/3/1/due + overdue)
- Discount codes, referrals, broadcast, CSV reports, AdminLog
- Jalali calendar reservation picker
- Alembic migrations through `0003`
- CI pytest workflow

## Open feature PRs (merge in this order)

| Order | PR | Branch | Migration | What it adds |
|------:|----|--------|-----------|--------------|
| 1 | [#4](https://github.com/mehrshadevilb-cell/RahYar-Academy-Management-System-V14/pull/4) | `ai/agent-hardening` | — | AI agent security lock, retries, policy |
| 2 | [#5](https://github.com/mehrshadevilb-cell/RahYar-Academy-Management-System-V14/pull/5) | `ai/support-system` | **0004** | Support tickets |
| 3 | [#6](https://github.com/mehrshadevilb-cell/RahYar-Academy-Management-System-V14/pull/6) | `ai/assignments` | **0005** | Homework assignments |
| 4 | [#7](https://github.com/mehrshadevilb-cell/RahYar-Academy-Management-System-V14/pull/7) | `ai/quizzes` | **0006** | Practice quizzes |
| 5 | [#9](https://github.com/mehrshadevilb-cell/RahYar-Academy-Management-System-V14/pull/9) | `ai/exams` | **0007** | Formal exams (pass % / attempt limit) |
| 6 | [#10](https://github.com/mehrshadevilb-cell/RahYar-Academy-Management-System-V14/pull/10) | `ai/class-reminders` | **0008** | Class session reminders |
| anytime | [#8](https://github.com/mehrshadevilb-cell/RahYar-Academy-Management-System-V14/pull/8) | `ai/student-progress` | — | Student progress dashboard |

**Closed without merge:** #2 (toy AI stubs), #3 (superseded by #4).

After each migration PR:

```bash
alembic upgrade head
```

See `docs/MERGE_ORDER.md` for conflict notes and post-merge checklist.

## Master-prompt coverage

| Area | Status |
|------|--------|
| Student registration / profiles | Done (`main`) |
| Product sales / payments / verification | Done (`main`) |
| SpotPlayer + ArtistYar delivery | Done (`main`) |
| Online classes / reservation / attendance | Done (`main`) |
| Installments + reminders | Done (`main`) |
| Discount codes / referrals | Done (`main`) |
| Broadcast / logs / reports | Done (`main`) |
| Support tickets | PR #5 |
| Assignments | PR #6 |
| Quizzes | PR #7 |
| Exams | PR #9 |
| Student progress | PR #8 |
| Class reminders | PR #10 |
| AI developer agent (hardened) | PR #4 |
| Live Telegram e2e tests | Still manual |

## Run checks

```bash
PYTHONPATH=. pytest -q
python -m compileall -q src tests
```

## Owner

RahYar Academy (`OWNER_ID` in `.env`)
