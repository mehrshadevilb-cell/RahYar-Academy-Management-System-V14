title: سفر هنرجو در بات
description: ثبت‌نام تا پرداخت، دوره، رزرو کلاس، تکلیف — تجربه روان
tools: read_file, list_tree
tags: design, ux

STUDENT JOURNEY UX SKILL:

Core student paths in RahYar:
1) Start / profile completion
2) Browse products & courses
3) Pay (card-to-card) → wait for approval → receive access (SpotPlayer / ArtistYar / online class)
4) My courses / progress
5) Reserve online class session
6) Homework submit / feedback
7) Support ticket
8) Referral

Design goals per step:
- Always show «where I am» and «what happens next»
- Payment: show amount, destination card (from settings), how to send receipt — never ask for CVV
- After payment submit: calm pending state; no false «paid» language until admin approves
- Access delivery: one clear message with link/license; retry button if integration fails
- Reservation: date/time visible; cancellation rules explained in plain Persian when relevant
- Homework: status PENDING / REVIEWED / RETURNED in human words

Friction reduction:
- Minimize steps in FSM; reuse known profile data
- Provide Back on every step
- If user sends wrong format, show an example once, not a lecture

Do not weaken enrollment, payment approval, or license rules for convenience.
