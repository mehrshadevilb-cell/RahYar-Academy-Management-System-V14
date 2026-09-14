FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Separate small file so Render/BuildKit cannot reuse a stale full-tree
# COPY cache when only Python sources changed in a prior layer key.
COPY docker-build-id.txt /tmp/rahyar-build-id.txt
COPY . .

ENV RAHYAR_BUILD_ID=20260915-chat-audit-v9-force-rebuild

CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
