# Deploy RahYar on Render

## Architecture

| Component | Render resource |
|-----------|-----------------|
| Bot + FastAPI health + reminder scheduler | **Web Service** (Docker, always-on) |
| PostgreSQL | **Managed Postgres** |
| Redis | Optional later (not required today) |

The app process is `python -m src.main`: HTTP on `$PORT`, Aiogram long-polling, and `InstallmentReminderScheduler`.

## Quick start (Blueprint)

1. Push `main` (includes `render.yaml`).
2. Render Dashboard → **New** → **Blueprint** → select this repo.
3. Apply the blueprint (`rahyar-bot` + `rahyar-db`).
4. Open the web service → **Environment** and set secrets marked `sync: false`:
   - `BOT_TOKEN`
   - `OWNER_ID`
   - `SPOTPLAYER_API_KEY` (if used)
   - `DEFAULT_CARD_NUMBER` / `DEFAULT_CARD_HOLDER`
5. Deploy and open `https://<service>.onrender.com/health` — expect `{"ok": true}`.
6. Message the bot on Telegram (`/start`).

## Manual deploy (without Blueprint)

1. **New → PostgreSQL** (same region as the web service).
2. **New → Web Service** → this GitHub repo → **Docker**.
3. Health check path: `/health`.
4. Plan: **Starter or higher** (not Free).
5. Env vars: same as in `render.yaml`.
6. `DATABASE_URL`: paste the **Internal** connection string from Postgres.

`postgres://` and `postgresql://` URLs are normalized automatically to
`postgresql+psycopg://` in `Settings` (see `normalize_database_url`).

## Critical rules

1. **Always-on instance** — Free tier sleeps; the bot stops receiving updates.
2. **Single replica** — multiple instances will fight over Telegram `getUpdates`.
3. **AI agent off** — keep `AI_AGENT_ENABLED=false` (no safe agent git sandbox on Render).
4. **Internal DB URL** — lower latency; use the internal hostname when the web service and DB share a region.
5. **Secrets only in Render** — never commit `.env`.

## Migrations

The Docker image starts with:

```bash
alembic upgrade head && python -m src.main
```

No separate migrate job is required for the first deploy.

## Optional Redis

Core features work without Redis. When you wire FSM storage or distributed locks, add a Render **Key Value** instance and set `REDIS_URL`.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Deploy fails on DB connect | `DATABASE_URL` set? Scheme normalized? DB in same region? |
| Bot silent | Logs for “Starting RahYar Bot”? Instance sleeping (Free plan)? |
| `getUpdates` conflict | Only one web instance running with this `BOT_TOKEN` |
| Telegram timeouts | Region blocked? Set `PROXY_URL` if you must |
| Health check failing | `/health` must return 200; ensure process binds `$PORT` |

## Local parity

```bash
docker compose up --build
# or
alembic upgrade head && python -m src.main
```
