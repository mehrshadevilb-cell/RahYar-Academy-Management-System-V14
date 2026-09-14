FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

ARG CACHE_BUST=20260915-schema-agentrouter-v4
COPY . .

CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
