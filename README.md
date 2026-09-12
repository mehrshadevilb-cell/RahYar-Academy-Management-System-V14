# RahYar Academy Management System — Production Final

Telegram LMS/CRM for RahYar Academy.

## Production deployment

1. Copy `.env.example` to `.env`.
2. Set `BOT_TOKEN`, `OWNER_ID`, `POSTGRES_PASSWORD`, `DATABASE_URL`, and other required values.
3. Use a strong unique PostgreSQL password and secret key.
4. Build and start:

```bash
docker compose up -d --build
```

The bot container waits for PostgreSQL and Redis health checks, runs:

```bash
alembic upgrade head
```

then starts the Telegram polling process. PostgreSQL data is stored in the named Docker volume `postgres_data`.

## Checks

```bash
python -m compileall -q src tests
PYTHONPATH=. pytest -q
```

## Backup

Back up PostgreSQL regularly. For example:

```bash
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > rahyar_backup.sql
```

Never commit `.env` or production secrets.
