# ============================================================================
# SEMAPA - Ingestor (watchdog de carpeta LoRaWAN → Cassandra)
# ============================================================================

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user -r requirements.txt

# ----- Runtime -----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH

WORKDIR /app

RUN useradd -m -u 1000 appuser

COPY --from=builder /root/.local /root/.local
COPY --chown=appuser:appuser . .

USER appuser

CMD ["python", "-u", "ingestor.py"]
