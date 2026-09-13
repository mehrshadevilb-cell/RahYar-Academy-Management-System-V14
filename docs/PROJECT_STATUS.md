# RahYar Academy Management System

## Status
Active development — v8 online-class workflow hardening completed.

## Completed
- Telegram bot boots with role-aware main menu and owner admin panel.
- Course listing/detail and manual card-to-card payment flow.
- Owner payment approval/rejection; access is granted only after approval.
- SpotPlayer license delivery with retry-on-failure flow.
- ArtistYar Telegram invite-link delivery with retry-on-failure flow.
- Online class enrollment (owner initiated) with monthly/term plans.
- Student online-class menu and reservation request flow.
- Owner reservation approval/rejection and attendance controls.
- **v8:** reservation ownership validation prevents a student from reserving another student's enrollment.
- **v8:** duplicate open reservations for the same enrollment/date/time are blocked.
- **v8:** attendance is idempotent per reservation; double-clicking cannot consume two sessions.
- **v8:** only confirmed reservations can receive attendance status.
- **v8:** PRESENT consumes one session; ABSENT/CANCELLED consume zero sessions.
- **v8:** reservation becomes COMPLETED when attendance is recorded.
- **v8:** enrollment automatically ends when remaining sessions reach zero.
- **v8:** owner has a dedicated "pending reservations" view in the admin panel.
- **v8:** automated tests added for the core online-class business rules.

## Still to build
- Broader integration/e2e tests (the CI workflow now runs the existing
  suite automatically, but end-to-end/live-bot testing is still manual).

## Recently completed (post-v8)
- Full admin CRUD for online-course pricing/teacher/session settings.
- Payment collection/reminders for monthly online-class installments.
- Product admin for SpotPlayer course IDs and ArtistYar channels.
- Discount codes (percentage/fixed, usage caps, expiry, reserve-on-apply /
  release-on-reject accounting so rejected receipts don't waste a usage slot).
- Admin action log (`AdminLog` + admin panel viewer/search) covering
  product, payment, license/ArtistYar retry, discount code, installment,
  and online-course/reservation/attendance actions.
- Broadcast (send any message type — text/photo/video/voice — to every
  linked student, with flood-control retry and a live progress counter).
- CSV report/export downloads for payments, students, online enrollments,
  and installments (`ReportService` + admin panel → "📊 خروجی گزارش‌ها").
- Alembic migrations (`alembic/`) — see `docs/MIGRATIONS.md` for adoption
  steps on an existing database.
- Fixed a bug where reservation confirm/reject always reported "already
  reviewed" because the pending-status check ran after the status had
  already been mutated by the service call.
- Jalali (Persian) calendar: a pure-Python, dependency-free conversion
  module (`src/core/utils/jalali.py`, round-trip tested for every day
  from 1940-2060, zero mismatches) plus an inline calendar-picker
  keyboard that replaced free-text date entry in the class reservation
  flow (`online_class.py`). Past dates are disabled in the picker and
  re-validated server-side on tap; navigation is clamped between the
  current month and 6 months ahead. Cleaned up a couple of leftover
  debug `print()` statements in `course.py` along the way.
- Referral system: every student gets a personal invite link
  (`/start ref_<telegram_id>`); when their invitee's first payment is
  approved, the referrer automatically receives a single-use 15%
  discount code (issued via the existing DiscountCodeService, so no
  new payment/credit infrastructure was needed). Self-referral and
  double-referral are structurally prevented, and the reward can only
  ever fire once per invitee (`Referral.status` PENDING -> REWARDED).
  New Alembic migration `0002_add_referrals_table`.
- Centralized error handling: a global `@dp.error()` handler now
  catches any exception that escapes a handler, logs it, tells the
  user something safely went wrong instead of crashing, and separately
  alerts the owner with the technical detail.
- Structured logging: `src/core/logging/logger.py` (previously an
  empty placeholder) now provides a real `get_logger()` used by the
  error handler and app startup, replacing a bare `print()` in `main.py`.
- CI: a GitHub Actions workflow (`.github/workflows/tests.yml`) now
  runs `pytest` automatically on every push/PR to main.

## Post-deployment fixes (first real production run, on Render + Postgres)
- **Critical bug fixed:** `payments.approved_by_id` was declared as a
  foreign key to `users.id`, but `PaymentService.approve()/reject()`
  has always stored the *admin's raw Telegram id* there (e.g.
  `8234306902`) instead. SQLite silently tolerated this (no FK
  enforcement, no fixed column width); Postgres correctly rejected it
  with `NumericValueOutOfRange`, which meant **no payment could ever be
  approved or rejected** once deployed. Fixed by dropping the mistaken
  FK and widening the column to `BigInteger` (model + new migration
  `0003_fix_payment_approved_by_id`, which looks up the real
  constraint name dynamically rather than assuming one). Renamed the
  service parameter `admin_id` -> `admin_telegram_id` so this exact
  confusion can't quietly recur.
- Restored the default-data seed calls and the installment reminder
  scheduler start-up, both of which had been dropped when `main.py`
  was adapted to also run a FastAPI health-check server for Render's
  web-service requirement. Also switched the health-check server from
  a hardcoded port to reading Render's `PORT` env var, and removed a
  duplicate/unused `src/web.py` left over from that adaptation.
- Course cover photos: the `Course.thumbnail` column existed but was
  never wired to anything. Admin panel now has "📷 تغییر عکس دوره"
  under each product; the course list and detail views send a photo
  with caption instead of plain text whenever one is set.
- Contact info at purchase time: `User.phone` and a `RegistrationState`
  FSM already existed but were never used anywhere, so admin payment
  notifications always showed "شماره تماس: ثبت نشده". Both purchase
  entry points ("💳 خرید دوره" and "🎁 دارم کد تخفیف") now collect full
  name + phone (Iranian mobile format, checked for uniqueness) from
  first-time buyers before proceeding, and skip straight through for
  anyone who already has both on file.

## Still to build
- Broader integration/e2e tests against a live bot instance (the CI
  workflow runs the existing unit/business-rule suite automatically,
  but nothing exercises the real Telegram API end-to-end yet).

## Run checks
```bash
PYTHONPATH=. pytest -q
python -m compileall -q src tests
```

## Owner
RahYar Academy (Owner Telegram ID configured in `.env` as `OWNER_ID`)
