"""Dashboard endpoints — KPIs por rol (Alcaldía / Gerencia / Contabilidad)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

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

    # Zonas críticas estrés hídrico (nivel ONU >= 5)
    zonas_estres = [p for p in per_capita if p["nivel_onu"] >= 5]

    # Alertas sobreconsumo: lecturas anómalas status >= 3
    alertas = 0
    try:
        rows = cassandra_client.execute_raw(
            "SELECT mac FROM lecturas_por_medidor WHERE status >= 3 LIMIT 5000 ALLOW FILTERING",
            profile="analytics")
        alertas = sum(1 for _ in rows)
    except Exception:
        pass

    # Calidad señal LoRaWAN: % medidores con gateway asignado
    n_med = n_gw = 0
    distritos_cubiertos: set = set()
    for r in cassandra_client.execute_raw(
        "SELECT distrito_id, gateway_id FROM medidores", profile="analytics"):
        n_med += 1
        if r.get("gateway_id") is not None:
            n_gw += 1
            distritos_cubiertos.add(r.get("distrito_id"))
    todos_distritos = set(hab.keys())
    sin_cobertura = sorted(todos_distritos - distritos_cubiertos)

    return {
        "poblacion_beneficiaria": poblacion,
        "consumo_total_m3": consumo_total,
        "consumo_per_capita_distrito": per_capita,
        "distribucion_niveles_onu": dict(niveles),
        "cobertura_pct": 100.0,
        "zonas_critico_estres_hidrico": zonas_estres,
        "alertas_sobreconsumo": alertas,
        "calidad_senal_lorawan_pct": round(n_gw * 100 / n_med, 2) if n_med else 0,
        "distritos_sin_cobertura": sin_cobertura,
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

    # Pico horario (consumo por hora del día)
    pico: dict[int, int] = defaultdict(int)
    for r in cassandra_client.execute_raw(
        "SELECT fecha_hora, consumo_m3 FROM lecturas_por_medidor LIMIT 20000", profile="analytics"):
        if r.get("fecha_hora"):
            pico[r["fecha_hora"].hour] += r.get("consumo_m3") or 0
    pico_max_hora = max(pico.items(), key=lambda x: x[1]) if pico else (0, 0)

    # Edad promedio medidores
    hoy = date.today()
    suma_dias = n_fechas = 0
    for r in cassandra_client.execute_raw(
        "SELECT fecha_instalacion FROM medidores", profile="analytics"):
        f = r.get("fecha_instalacion")
        if not f:
            continue
        if hasattr(f, "date"):
            f = f.date()
        try:
            suma_dias += (hoy - f).days
            n_fechas += 1
        except Exception:
            continue
    edad_promedio_anios = round(suma_dias / n_fechas / 365.25, 1) if n_fechas else 0

    # Lecturas registradas por app móvil (obligatorio)
    n_lect_app = 0
    try:
        rows = cassandra_client.execute_raw(
            "SELECT mac FROM lecturas_manuales LIMIT 10000", profile="analytics")
        n_lect_app = sum(1 for _ in rows)
    except Exception:
        pass

    return {
        "medidores_por_modelo": {str(k): v for k, v in c_modelo.items()},
        "fallas_por_modelo": {str(k): v for k, v in falla_modelo.items()},
        "top10_zonas_consumo": [{"zona": z, "consumo_m3": v} for z, v in top10],
        "consumo_acumulado_m3": consumo_total,
        "pico_max_hora": {"hora": pico_max_hora[0], "consumo_m3": pico_max_hora[1]},
        "pico_horario": [{"hora": h, "consumo_m3": v} for h, v in sorted(pico.items())],
        "edad_promedio_medidores_anios": edad_promedio_anios,
        "lecturas_app_movil": n_lect_app,
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

    # Facturación por categoría tarifaria
    fact_cat: dict[str, float] = defaultdict(float)
    for r in cassandra_client.execute_raw(
        "SELECT categoria_tarifa, monto_bs FROM facturas_por_periodo", profile="analytics"):
        fact_cat[r.get("categoria_tarifa") or "?"] += float(r.get("monto_bs") or 0)

    # Aging deuda: facturas PENDIENTE por edad (periodo vs hoy)
    aging = {"0-30": 0, "31-60": 0, "61-90": 0, "+90": 0}
    hoy = date.today()
    try:
        for r in cassandra_client.execute_raw(
            "SELECT periodo, monto_bs, estado FROM facturas WHERE estado='PENDIENTE' "
            "LIMIT 10000 ALLOW FILTERING", profile="analytics"):
            try:
                y, m = map(int, r["periodo"].split("-"))
                fp = date(y, m, 1)
                dias = (hoy - fp).days
                monto = float(r.get("monto_bs") or 0)
                if dias <= 30:
                    aging["0-30"] += monto
                elif dias <= 60:
                    aging["31-60"] += monto
                elif dias <= 90:
                    aging["61-90"] += monto
                else:
                    aging["+90"] += monto
            except Exception:
                continue
    except Exception:
        pass

    # Preavisos emitidos + efectividad canal (últimos 30 días)
    preavisos_por_canal = {"email": {"ENVIADO": 0, "FALLO": 0},
                           "sms": {"ENVIADO": 0, "FALLO": 0},
                           "whatsapp": {"ENVIADO": 0, "FALLO": 0}}
    total_preavisos = 0
    try:
        for i in range(31):
            d = hoy - timedelta(days=i)
            try:
                for r in cassandra_client.execute_raw(
                    "SELECT canal, estado FROM preavisos_log WHERE fecha = %s", (d,),
                    profile="analytics"):
                    canal = (r.get("canal") or "").lower()
                    estado = r.get("estado") or "?"
                    if canal in preavisos_por_canal and estado in ("ENVIADO", "FALLO"):
                        preavisos_por_canal[canal][estado] += 1
                        total_preavisos += 1
            except Exception:
                continue
    except Exception:
        pass

    efectividad_canal = {}
    for canal, cnt in preavisos_por_canal.items():
        tot = cnt["ENVIADO"] + cnt["FALLO"]
        efectividad_canal[canal] = {
            "enviados": cnt["ENVIADO"], "fallos": cnt["FALLO"],
            "tasa_exito_pct": round(cnt["ENVIADO"] * 100 / tot, 2) if tot else 0,
        }

    return {
        "medidores_activos_por_categoria": dict(c_cat),
        "facturado_bs": round(facturado_bs, 2),
        "recaudado_bs": round(recaudado_bs, 2),
        "cartera_vencida_bs": round(pendiente_bs, 2),
        "pct_recuperacion": round(recaudado_bs * 100 / facturado_bs, 2) if facturado_bs else 0,
        "contratos_morosos": morosos,
        "facturado_por_distrito": {str(k): round(v, 2) for k, v in sorted(por_distrito.items())},
        "facturado_por_categoria_tarifa": {k: round(v, 2) for k, v in fact_cat.items()},
        "aging_deuda_bs": {k: round(v, 2) for k, v in aging.items()},
        "preavisos_emitidos_30d": total_preavisos,
        "preavisos_por_canal": preavisos_por_canal,
        "efectividad_por_canal": efectividad_canal,
    }
