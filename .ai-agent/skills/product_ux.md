# Skill: Product UX (Academy)

## User journeys to protect
1. Discover course → order → pending payment → owner approve in Telegram → access
2. Discover online class → inquiry/reservation → confirm → attendance
3. Student login → panel → see courses/reservations → link Telegram later
4. Admin login → today report → pending payments/reservations

## Rules
- Never grant digital access from the website alone
- Pending is a first-class status; show it clearly
- Confirmation steps for destructive admin actions
- Demo auth is OK until real API auth ships; label demo accounts
- Loading / empty / error states required on every data view

## Forms
- Minimal fields (name, phone 09xxxxxxxxx, optional note)
- Validate client-side lightly; trust API error messages in Persian
- Success copy must say what happens next (e.g. wait for admin)

## Navigation
Public: Home, Courses, Online, Assistant, About, Contact, Login
Student: Overview, Courses, Reservations, Profile
Admin: Dashboard, Payments, Reservations, Students, AI, System
