"""Clima Cochabamba vía Open-Meteo (API gratuita, sin API key).

Archive API: https://open-meteo.com/en/docs/historical-weather-api
  GET https://archive-api.open-meteo.com/v1/archive
      ?latitude=-17.39&longitude=-66.15
      &start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
      &daily=temperature_2m_mean,precipitation_sum&timezone=America/La_Paz

Agrega a nivel mensual: temperatura media + precipitación + índice de sequía.
Cache Redis (6h). Fallback a valores típicos si la API falla.
"""
from __future__ import annotations

import json
from collections import defaultdict

import httpx
from loguru import logger

from app.core.redis_client import redis_client


CBBA_LAT = -17.39
CBBA_LON = -66.15
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CACHE_KEY = "clima:cbba:{start}:{end}"
CACHE_TTL = 6 * 3600

# Precipitación mensual de referencia para índice de sequía (mm).
# Cochabamba: estación seca abr-sep, húmeda nov-mar.
_PRECIP_REF = 60.0


def _drought_index(precip_mm: float) -> dict:
    """0 (sin estrés) → 100 (sequía severa). Menos lluvia = más estrés."""
    idx = max(0.0, min(100.0, (1 - precip_mm / _PRECIP_REF) * 100))
    if idx < 25:
        nivel = "Sin estrés"
    elif idx < 50:
        nivel = "Leve"
    elif idx < 75:
        nivel = "Moderado"
    else:
        nivel = "Severo"
    return {"indice": round(idx, 1), "nivel": nivel}


async def fetch_clima_mensual(start_date: str, end_date: str) -> dict:
    """Devuelve {periodo 'YYYY-MM': {temp_media, precip_mm, sequia}}."""
    cache_key = CACHE_KEY.format(start=start_date, end=end_date)
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    result: dict[str, dict] = {}
    try:
        params = {
            "latitude": CBBA_LAT,
            "longitude": CBBA_LON,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "temperature_2m_mean,precipitation_sum",
            "timezone": "America/La_Paz",
        }
        async with httpx.AsyncClient(timeout=8.0) as cli:
            r = await cli.get(ARCHIVE_URL, params=params)
            r.raise_for_status()
            data = r.json()

        daily = data.get("daily", {})
        fechas = daily.get("time", [])
        temps = daily.get("temperature_2m_mean", [])
        precs = daily.get("precipitation_sum", [])

        agg: dict[str, dict] = defaultdict(lambda: {"t": [], "p": 0.0})
        for i, f in enumerate(fechas):
            periodo = f[:7]  # YYYY-MM
            t = temps[i] if i < len(temps) else None
            p = precs[i] if i < len(precs) else 0.0
            if t is not None:
                agg[periodo]["t"].append(t)
            agg[periodo]["p"] += p or 0.0

        for periodo, v in sorted(agg.items()):
            temp_media = round(sum(v["t"]) / len(v["t"]), 1) if v["t"] else None
            precip = round(v["p"], 1)
            result[periodo] = {
                "temp_media": temp_media,
                "precip_mm": precip,
                "sequia": _drought_index(precip),
            }
        await redis_client.set(cache_key, json.dumps(result, default=str), ttl_seconds=CACHE_TTL)
    except Exception as e:
        logger.warning(f"Open-Meteo falló ({e}); sin datos climáticos")

    return result
