# RahYar AI Skill: Testing

1. Critical rules testable without Telegram.
2. Prefer service-level tests for payments, licenses, reservations, installments.
3. Do not weaken tests to force green.
4. Before PR: compileall + pytest.
5. Cover cancelled sessions, overdue installments, duplicate confirmations.
6. Minimal deterministic fixtures.
7. Keep models and migrations aligned.
8. UI copy changes still need handler smoke checks.
9. Report residual risk in PR summary.
10. Add reproduction before claiming a bug fixed.
