"""Dashboard endpoints — KPIs por rol (Alcaldía / Gerencia / Contabilidad)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends

from app.core.cassandra_client import cassandra_client
from app.core.redis_client import redis_client
from app.core.security import (ROLE_ALCALDIA, ROLE_CONTABILIDAD, ROLE_GERENCIA,
                               current_user)


router = APIRouter()

ESTADOS_ACTIVOS = {"Operativo", "Reacondicionado", "Nuevo"}
ESTADOS_FALLA = {"Dañado"}
ESTADOS_MANTEN = {"Mantenimiento"}
RESIDENCIALES = {"R1", "R2", "R3", "R4"}


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
    base = await _cached_kpi("dash:base", _base_kpis, ttl=90)
    if rol == ROLE_ALCALDIA:
        return {**base, **await _cached_kpi("dash:alcaldia", _kpis_alcaldia, ttl=180)}
    if rol == ROLE_GERENCIA:
        return {**base, **await _cached_kpi("dash:gerencia", _kpis_gerencia, ttl=120)}
    if rol == ROLE_CONTABILIDAD:
        return {**base, **await _cached_kpi("dash:contab", _kpis_contab, ttl=120)}
    return base


# Endpoints dedicados por dashboard (frontend los consume directamente)
@router.get("/alcaldia")
async def dash_alcaldia(_u: dict = Depends(current_user)):
    return {**await _cached_kpi("dash:base", _base_kpis, 90),
            **await _cached_kpi("dash:alcaldia", _kpis_alcaldia, 180)}


@router.get("/gerencia")
async def dash_gerencia(_u: dict = Depends(current_user)):
    return {**await _cached_kpi("dash:base", _base_kpis, 90),
            **await _cached_kpi("dash:gerencia", _kpis_gerencia, 120)}


@router.get("/contabilidad")
async def dash_contab(_u: dict = Depends(current_user)):
    return {**await _cached_kpi("dash:base", _base_kpis, 90),
            **await _cached_kpi("dash:contab", _kpis_contab, 120)}


# ----------------------------------------------------------------------------
def _base_kpis():
    c_estado = Counter()
    for r in cassandra_client.execute_raw("SELECT estado FROM medidores", profile="analytics"):
        c_estado[r["estado"]] += 1
    total = sum(c_estado.values())
    activos = sum(c_estado.get(e, 0) for e in ESTADOS_ACTIVOS)
    falla = sum(c_estado.get(e, 0) for e in ESTADOS_FALLA)
    manten = sum(c_estado.get(e, 0) for e in ESTADOS_MANTEN)
    return {
        "medidores_total": total,
        "medidores_activos": activos,
        "medidores_falla": falla,
        "medidores_mantenimiento": manten,
        "pct_sensores_falla": round(falla * 100 / total, 2) if total else 0,
        "medidores_por_estado": dict(c_estado),
    }


def _nivel_onu(lpd: float) -> int:
    for tope, nivel in [(100, 1), (180, 2), (250, 3), (300, 4), (400, 5)]:
        if lpd <= tope:
            return nivel
    return 6


def _kpis_alcaldia():
    # Población + consumo por distrito → per cápita + niveles ONU
    hab = {}
    for r in cassandra_client.execute_raw("SELECT distrito_id, habitantes FROM distritos", profile="analytics"):
        hab[r["distrito_id"]] = r["habitantes"] or 0
    poblacion = sum(hab.values())

    consumo_dist: dict[int, int] = defaultdict(int)
    consumo_total = 0
    for r in cassandra_client.execute_raw(
        "SELECT distrito_id, consumo_m3 FROM lecturas_por_zona_periodo", profile="analytics"):
        consumo_dist[r["distrito_id"]] += r["consumo_m3"] or 0
        consumo_total += r["consumo_m3"] or 0

    per_capita = []
    niveles = Counter()
    for d, m3 in sorted(consumo_dist.items()):
        h = hab.get(d, 0)
        lpd = round(m3 * 1000 / (90 * h), 1) if h else 0
        nivel = _nivel_onu(lpd)
        niveles[nivel] += 1
        per_capita.append({"distrito_id": d, "litros_persona_dia": lpd, "nivel_onu": nivel})

    return {
        "poblacion_beneficiaria": poblacion,
        "consumo_total_m3": consumo_total,
        "consumo_per_capita_distrito": per_capita,
        "distribucion_niveles_onu": dict(niveles),
        "cobertura_pct": 100.0,
    }


def _kpis_gerencia():
    c_modelo = Counter()
    falla_modelo: dict[int, dict[str, int]] = defaultdict(lambda: {"total": 0, "fallas": 0})
    for r in cassandra_client.execute_raw("SELECT tipo_medidor_id, estado FROM medidores", profile="analytics"):
        mid = r["tipo_medidor_id"]
        c_modelo[mid] += 1
        falla_modelo[mid]["total"] += 1
        if r["estado"] not in ESTADOS_ACTIVOS:
            falla_modelo[mid]["fallas"] += 1

    # Top 10 zonas por consumo
    zona_cons: dict[str, int] = defaultdict(int)
    consumo_total = 0
    for r in cassandra_client.execute_raw(
        "SELECT distrito_id, zona, consumo_m3 FROM lecturas_por_zona_periodo", profile="analytics"):
        zona_cons[f"D{r['distrito_id']}-{r['zona']}"] += r["consumo_m3"] or 0
        consumo_total += r["consumo_m3"] or 0
    top10 = sorted(zona_cons.items(), key=lambda x: -x[1])[:10]

    return {
        "medidores_por_modelo": {str(k): v for k, v in c_modelo.items()},
        "fallas_por_modelo": {str(k): v for k, v in falla_modelo.items()},
        "top10_zonas_consumo": [{"zona": z, "consumo_m3": v} for z, v in top10],
        "consumo_acumulado_m3": consumo_total,
    }


def _kpis_contab():
    # Facturación por categoría + estado (desde lecturas: proxy si no hay facturas)
    c_cat = Counter()
    for r in cassandra_client.execute_raw(
        "SELECT subcategoria, estado FROM medidores", profile="analytics"):
        if r["estado"] in ESTADOS_ACTIVOS:
            c_cat[r["subcategoria"] or "?"] += 1

    # Facturas: facturado / recaudado / mora
    facturado_bs = 0.0
    recaudado_bs = 0.0
    pendiente_bs = 0.0
    por_distrito: dict[int, float] = defaultdict(float)
    morosos = 0
    for r in cassandra_client.execute_raw(
        "SELECT distrito_id, monto_bs, estado FROM facturas_por_periodo", profile="analytics"):
        m = float(r["monto_bs"] or 0)
        facturado_bs += m
        por_distrito[r["distrito_id"]] += m
        if r["estado"] == "PAGADA":
            recaudado_bs += m
        else:
            pendiente_bs += m
            morosos += 1

    return {
        "medidores_activos_por_categoria": dict(c_cat),
        "facturado_bs": round(facturado_bs, 2),
        "recaudado_bs": round(recaudado_bs, 2),
        "cartera_vencida_bs": round(pendiente_bs, 2),
        "pct_recuperacion": round(recaudado_bs * 100 / facturado_bs, 2) if facturado_bs else 0,
        "contratos_morosos": morosos,
        "facturado_por_distrito": {str(k): round(v, 2) for k, v in sorted(por_distrito.items())},
    }
