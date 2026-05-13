"""Cotización USD→BOB con cache Redis.

Provider apilayer/exchangerate.host (https://docs.apilayer.com/exchangerate).
Endpoint: GET /live?source=USD&currencies=BOB → quotes.USDBOB
Auth: header `apikey: <key>` (también acepta query `access_key=<key>`).

Fallback: USD_FALLBACK_RATE si la API responde error o tarda > 5s.
"""
from __future__ import annotations

import json
from datetime import datetime

import httpx
from loguru import logger

from app.core.config import settings
from app.core.redis_client import redis_client


CACHE_KEY = "usd:bob:latest"


async def fetch_usd_bob() -> dict:
    """Devuelve {rate, source, fetched_at}. Cachea en Redis por USD_CACHE_TTL."""
    cached = await redis_client.get(CACHE_KEY)
    if cached:
        return json.loads(cached)

    rate: float
    source: str
    try:
        headers = {}
        url = settings.USD_API_URL
        if settings.USD_API_KEY:
            headers["apikey"] = settings.USD_API_KEY
        async with httpx.AsyncClient(timeout=5.0) as cli:
            r = await cli.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
        # apilayer schema: {success, source:"USD", quotes:{USDBOB: 6.96}, ...}
        if "quotes" in data and "USDBOB" in data["quotes"]:
            rate = float(data["quotes"]["USDBOB"])
            source = "apilayer.exchangerate.host"
        # legacy exchangerate.host schema: {rates:{BOB:6.96}}
        elif "rates" in data and "BOB" in data["rates"]:
            rate = float(data["rates"]["BOB"])
            source = "exchangerate.host"
        else:
            raise ValueError(f"Schema USD desconocido: {list(data.keys())}")
    except Exception as e:
        logger.warning(f"USD API falló ({e}); usando fallback {settings.USD_FALLBACK_RATE}")
        rate = settings.USD_FALLBACK_RATE
        source = "fallback"

    payload = {
        "rate": rate,
        "source": source,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    await redis_client.set(CACHE_KEY, json.dumps(payload), ttl_seconds=settings.USD_CACHE_TTL)
    return payload
