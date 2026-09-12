# Database Migrations (Alembic)

RahYar now uses Alembic for schema changes. `src/database/init_db.py`
(`Base.metadata.create_all()`) still runs at bot startup for local/dev
convenience, but it can only *add* missing tables — it can never alter an
existing column, constraint, or index. Alembic is what actually manages
schema evolution from here on.

## One-time setup per environment

**Brand-new, empty database** (new dev machine, new staging env):

```bash
pip install -r requirements.txt
alembic upgrade head
```

This creates the full current schema (all 18 tables) in one step.

**Existing database that already has these tables** (any dev DB you've
been running with `init_database()` before this change, or a production
DB you consider stable):

```bash
alembic stamp head
```

`stamp` records "this DB is already at revision 0001" without touching a
single table. Do **not** run `upgrade head` on a DB that already has the
tables — it will try to `CREATE TABLE` things that exist and fail.

If you're not sure which case you're in: `alembic current` prints nothing
on a DB Alembic has never touched. If your tables already exist, `stamp`;
otherwise `upgrade head`.

## Making a schema change from now on

1. Change the SQLAlchemy model(s) in `src/database/models/`.
2. Generate a migration:
   ```bash
   alembic revision --autogenerate -m "add teacher_phone to online_course"
   ```
3. **Open the generated file in `alembic/versions/` and read it.**
   Autogenerate is a starting point, not a guarantee — it does not
   reliably detect: column renames (it will see these as a drop + add,
   destroying data), check constraints, or some enum changes. Fix the
   migration by hand when that happens.
4. For anything destructive (dropping/renaming a column, tightening a
   constraint on a table with existing rows), write the data migration
   explicitly — don't let autogenerate silently drop data. See Rule 25/32
   in `PROJECT_CONTEXT.md`.
5. Run it locally: `alembic upgrade head`.
6. Confirm `alembic downgrade -1` also works cleanly before committing,
   so a bad deploy can actually be rolled back.
7. Commit the migration file together with the model change, in the same
   PR/commit — a model change without its migration is an incomplete
   change per this project's Definition of Done.

## Useful commands

```bash
alembic current          # what revision is this DB at
alembic history           # list all revisions
alembic upgrade head      # apply all pending migrations
alembic downgrade -1       # roll back the most recent migration
alembic upgrade head --sql # print the SQL without executing (review before running on prod)
```

## Rules

- Never edit a migration that has already been applied anywhere outside
  your own machine — add a new migration instead.
- Never call `Base.metadata.create_all()` against a production database.
  It is a dev-only convenience in `init_db.py`.
- One logical schema change per migration, matching the commit-message
  conventions in `PROJECT_CONTEXT.md` §33.
