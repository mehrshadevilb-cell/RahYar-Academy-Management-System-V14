FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

ARG CACHE_BUST=20260915-pg-enum-labels-v7
COPY . .

CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
