# Public sales website (linked to Telegram bot)

The FastAPI process serves both:

1. **Persian storefront** — `/`, `/products`, `/classes`
2. **Health** — `/health` (Render)
3. **Telegram bot** — long-polling in the same container

## Shared data

| Web | Bot / DB |
|-----|----------|
| Digital products | `courses` (same active catalog) |
| Online classes | `online_courses` |
| Order form | Creates `users` (by phone) + `payments` (`pending`) |
| Class inquiry | Notifies owner; enrollment still admin-only |
| Card info | Active `payment_cards` row |

**Access is never granted from the website.** Owner approves payments in Telegram like bot receipts.

## Deep links

Set `BOT_USERNAME` (without `@`).

| Link | Effect in bot |
|------|----------------|
| `t.me/<bot>?start=buy_<product_id>` | Shows product purchase hint |
| `t.me/<bot>?start=class_<course_id>` | Shows online-class hint |

## Env

```env
BOT_USERNAME=YourBotUsername
SITE_NAME=آکادمی راه‌یار
SITE_TAGLINE=...
```

## Deploy

Same Render Web Service as the bot. After deploy, open `https://<service>.onrender.com/`.

Routes:

- `GET /` — home
- `GET /products`, `GET /products/{id}`, `POST /products/{id}/order`
- `GET /classes`, `GET /classes/{id}`, `POST /classes/{id}/inquiry`
- `GET /go-bot` — redirect to Telegram
- `GET /health` — health check
