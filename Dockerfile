FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Cache-bust marker so Render always re-COPY source after storefront fixes.
ARG CACHE_BUST=20260914-storefront-v2
COPY . .

CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
