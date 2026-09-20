FROM python:3.13-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY docker-build-id.txt /tmp/rahyar-build-id.txt
COPY . .

ENV RAHYAR_BUILD_ID=20260921-migrate-boot-v1

# migrate_boot: if production DB already has schema but empty alembic_version,
# stamp head first, then upgrade. Avoids DuplicateTable/DuplicateObject loops.
CMD ["sh", "-c", "python scripts/migrate_boot.py && python -m src.main"]
