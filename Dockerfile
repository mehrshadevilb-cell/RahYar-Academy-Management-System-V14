FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY docker-build-id.txt /tmp/rahyar-build-id.txt
COPY . .

ENV RAHYAR_BUILD_ID=20260915-payment-review-v10

CMD ["sh", "-c", "alembic upgrade head && python -m src.main"]
