# SEMAPA - Worker SMS (RabbitMQ → mock Twilio)
FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim AS runtime
ENV PATH=/root/.local/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd -m -u 1000 appuser
COPY --from=builder /root/.local /root/.local
COPY --chown=appuser:appuser . .
USER appuser
CMD ["python", "-u", "worker.py"]
