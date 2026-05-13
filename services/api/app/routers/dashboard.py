"""Dashboard endpoints — KPIs filtrados por rol."""
from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, Depends

from app.core.cassandra_client import cassandra_client
from app.core.redis_client import redis_client
from app.core.security import (ROLE_ALCALDIA, ROLE_CONTABILIDAD, ROLE_GERENCIA,
                               current_user)


router = APIRouter()


async def _cached_kpi(key: str, fn, ttl: int = 60):
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    value = fn()
    await redis_client.set(key, json.dumps(value, default=str), ttl_seconds=ttl)
    return value


@router.get("/kpis")
async def kpis(user: dict = Depends(current_user)):
    rol = user["rol"]
    base = await _cached_kpi("dash:base", _base_kpis, ttl=60)
    if rol == ROLE_ALCALDIA:
        return {**base, **await _cached_kpi("dash:alcaldia", _kpis_alcaldia, ttl=120)}
    if rol == ROLE_GERENCIA:
        return {**base, **await _cached_kpi("dash:gerencia", _kpis_gerencia, ttl=60)}
    if rol == ROLE_CONTABILIDAD:
        return {**base, **await _cached_kpi("dash:contab", _kpis_contab, ttl=120)}
    return base


def _base_kpis():
    n_medidores = sum(1 for _ in cassandra_client.execute_raw(
        "SELECT medidor_id FROM medidores", profile="analytics"
    ))
    c_estado = Counter()
    for r in cassandra_client.execute_raw(
        "SELECT estado FROM medidores", profile="analytics"
    ):
        c_estado[r["estado"]] += 1
    return {
        "medidores_total": n_medidores,
        "medidores_activos": c_estado.get("ACTIVO", 0),
        "medidores_inactivos": c_estado.get("INACTIVO", 0),
        "medidores_fuera_servicio": c_estado.get("FUERA_SERVICIO", 0),
    }


def _kpis_alcaldia():
    poblacion = 0
    for r in cassandra_client.execute_raw("SELECT habitantes FROM distritos", profile="analytics"):
        poblacion += r.get("habitantes") or 0
    return {
        "poblacion_beneficiaria": poblacion,
        "cobertura": "100% urbano (proxy)",
    }


def _kpis_gerencia():
    c_modelo = Counter()
    for r in cassandra_client.execute_raw("SELECT modelo_id FROM medidores", profile="analytics"):
        c_modelo[r["modelo_id"]] += 1
    return {
        "medidores_por_modelo": dict(c_modelo),
    }


def _kpis_contab():
    c_cat = Counter()
    for r in cassandra_client.execute_raw(
        "SELECT categoria_tarifa FROM medidores WHERE estado='ACTIVO' ALLOW FILTERING",
        profile="analytics",
    ):
        c_cat[r["categoria_tarifa"]] += 1
    return {
        "medidores_activos_por_categoria": dict(c_cat),
    }
