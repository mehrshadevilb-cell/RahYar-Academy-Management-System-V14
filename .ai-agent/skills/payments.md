# RahYar AI Skill: Payments & Installments

1. Payment provider behind abstraction.
2. Explicit states: pending, submitted, approved, rejected, cancelled, refunded.
3. Never mark paid only because the user claims payment.
4. Card-to-card details from settings, not hardcoded.
5. Secure receipt handling; no sensitive financial spam in logs.
6. Installment reminders service-driven and testable.
7. License access follows approved payment rules.
8. Discount/referral limits validated server-side.
9. Idempotent confirmation against duplicate entitlements.
10. Persian owner messages; English internal enums/paths.
