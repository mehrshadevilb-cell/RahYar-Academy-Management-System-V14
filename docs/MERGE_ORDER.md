# Merge order for pending LMS PRs

## Recommended sequence

1. **PR #4** — AI agent hardening (no migration; independent)
2. **PR #5** — Support → Alembic `0004`
3. **PR #6** — Assignments → Alembic `0005` (depends on `0004`)
4. **PR #7** — Quizzes → Alembic `0006` (depends on `0005`)
5. **PR #9** — Exams → Alembic `0007` (depends on `0006`)
6. **PR #10** — Class reminders → Alembic `0008` (depends on `0007`)
7. **PR #8** — Student progress (no migration; merge anytime)

## After each merge with a migration

```bash
git checkout main && git pull
alembic upgrade head
PYTHONPATH=. pytest -q
```

## Menu wiring note

Feature branches each add their own menu buttons independently. After several
merges you may need a small follow-up commit on `main` that unions all student
menu items and admin panel buttons (support, assignments, quizzes, exams,
progress) into a single `main_menu.py` / `admin_menu_keyboard.py` / `bot.py`.

Suggested final student menu keys:

- 📚 دوره ها
- 🎓 دوره های من
- 🎼 کلاس آنلاین
- 📝 تکالیف
- ❓ آزمون‌ها
- 📋 آزمون رسمی
- 📈 پیشرفت من
- 👤 پروفایل
- 🎁 دعوت از دوستان
- 🆘 پشتیبانی

## Do not merge

- PR #2 — toy `src/ai_agent` stubs (closed)
- PR #3 — superseded production audit (closed; healthcheck lives in #4)

## Post-merge polish (optional)

- Extend `ProgressService` with assignment / quiz / exam scores
- Live Telegram e2e smoke tests
- Owner review of AI agent with `AI_AGENT_ENABLED=false` default kept
