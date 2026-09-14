FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Cache-bust so Render rebuilds after storefront/migration fixes.
ARG CACHE_BUST=20260915-storefront-template-v3
COPY . .

CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
