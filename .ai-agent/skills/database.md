# RahYar AI Skill: Database

1. PostgreSQL is the source of truth.
2. Schema changes need new Alembic migrations; never rewrite applied revisions.
3. Prefer existing UUID/key patterns.
4. Foreign keys, unique constraints, indexes deliberately.
5. Avoid N+1; use joins/selectinload when needed.
6. Transactions for multi-record operations.
7. Explicit status fields.
8. No casual destructive migrations.
9. Timezone-aware datetimes for scheduling.
10. Do not store permanent business data only in Redis.
