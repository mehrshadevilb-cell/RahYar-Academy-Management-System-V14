# RahYar AI Skill: Architecture

1. Handlers thin; services own business rules; repositories own persistence.
2. Telegram layer must not contain business logic or direct SQL.
3. Prefer existing services over parallel modules.
4. Payments, licenses, reservations, installments stay explicit and testable.
5. Products should be data-driven, not hardcoded if/else trees.
6. External systems behind integration modules.
7. FSM for multi-step UX only; durable state in PostgreSQL.
8. Async SQLAlchemy + Alembic; never create_all in production.
9. Small typed modules without circular imports.
10. Smallest architecture-preserving change over rewrites.
