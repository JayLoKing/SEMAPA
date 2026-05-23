"""Consultas analíticas (modelo MAC-céntrico, data real).

CL=ONE para analítica + cache Redis (TTL configurable).
Estados de medidor: Operativo|Reacondicionado|Nuevo (activos),
Mantenimiento, Dañado (falla).
Consumo en m³ (lecturas reales: LecturaActual - lecturaAnterior).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.cassandra_client import cassandra_client
from app.core.redis_client import redis_client
from app.core.security import current_user
from app.services.clima_service import fetch_clima_mensual


router = APIRouter()

CACHE_TTL = 60

# Estados de medidor reales
ESTADOS_ACTIVOS = {"Operativo", "Reacondicionado", "Nuevo"}
ESTADOS_FALLA = {"Dañado"}
ESTADOS_MANTEN = {"Mantenimiento"}
RESIDENCIALES = {"R1", "R2", "R3", "R4"}


async def _cached(key: str, fn, ttl: int = CACHE_TTL):
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    value = fn()
    await redis_client.set(key, json.dumps(value, default=str), ttl_seconds=ttl)
    return value


def _es_activo(estado: str) -> bool:
    return estado in ESTADOS_ACTIVOS


# ----------------------------------------------------------------------------
# 1. Consumo total por distrito (periodo)
# ----------------------------------------------------------------------------
@router.get("/consumo-promedio-distrito")
async def consumo_promedio_distrito(_u: dict = Depends(current_user)):
    def _q():
        out: dict[int, dict[str, Any]] = defaultdict(lambda: {"total": 0, "n": 0})
        rows = cassandra_client.execute_raw(
            "SELECT distrito_id, consumo_m3 FROM lecturas_por_zona_periodo",
            profile="analytics",
        )
        for r in rows:
            out[r["distrito_id"]]["total"] += r["consumo_m3"] or 0
            out[r["distrito_id"]]["n"] += 1
        return [
            {"distrito_id": d, "consumo_total_m3": v["total"],
             "promedio_m3": round(v["total"] / v["n"], 2) if v["n"] else 0, "muestras": v["n"]}
            for d, v in sorted(out.items())
        ]
    return await _cached("q:cpd", _q, ttl=120)


# ----------------------------------------------------------------------------
# 2. Comparativa por periodo entre distritos
# ----------------------------------------------------------------------------
@router.get("/comparativa-semanas")
async def comparativa_semanas(distritos: str = Query("1,3,5"), _u: dict = Depends(current_user)):
    ids = [int(x) for x in distritos.split(",") if x.strip().isdigit()]
    def _q():
        agg: dict[tuple[int, str], int] = defaultdict(int)
        rows = cassandra_client.execute_raw(
            "SELECT distrito_id, periodo, consumo_m3 FROM lecturas_por_zona_periodo",
            profile="analytics",
        )
        for r in rows:
            if r["distrito_id"] not in ids:
                continue
            agg[(r["distrito_id"], r["periodo"])] += r["consumo_m3"] or 0
        return [
            {"distrito_id": d, "periodo": p, "consumo_m3": v}
            for (d, p), v in sorted(agg.items())
        ]
    return await _cached(f"q:csem:{distritos}", _q)


# ----------------------------------------------------------------------------
# 3. Consumos excesivos (>150 m³ acumulado en el periodo)
# ----------------------------------------------------------------------------
@router.get("/consumos-excesivos")
async def consumos_excesivos(umbral_m3: int = 50, _u: dict = Depends(current_user)):
    def _q():
        agg: dict[str, int] = defaultdict(int)
        rows = cassandra_client.execute_raw(
            "SELECT mac, consumo_m3 FROM lecturas_por_zona_periodo", profile="analytics",
        )
        for r in rows:
            agg[r["mac"]] += r["consumo_m3"] or 0
        return sorted(
            [{"mac": k, "consumo_m3": v} for k, v in agg.items() if v > umbral_m3],
            key=lambda x: -x["consumo_m3"],
        )[:200]
    return await _cached(f"q:excesivos:{umbral_m3}", _q, ttl=120)


# ----------------------------------------------------------------------------
# 4/5. Medidores por estado
# ----------------------------------------------------------------------------
@router.get("/medidores-activos")
async def medidores_activos(_u: dict = Depends(current_user)):
    def _q():
        rows = cassandra_client.execute_raw("SELECT estado FROM medidores", profile="analytics")
        c = Counter(r["estado"] for r in rows)
        total = sum(c.values())
        activos = sum(c.get(e, 0) for e in ESTADOS_ACTIVOS)
        return {"total": total, "activos": activos,
                "falla": sum(c.get(e, 0) for e in ESTADOS_FALLA),
                "mantenimiento": sum(c.get(e, 0) for e in ESTADOS_MANTEN),
                "por_estado": dict(c)}
    return await _cached("q:medidores_activos", _q, ttl=120)


@router.get("/medidores-fuera-servicio")
async def medidores_fuera_servicio(_u: dict = Depends(current_user)):
    def _q():
        rows = cassandra_client.execute_raw(
            "SELECT mac, distrito_id, zona, estado FROM medidores WHERE estado='Dañado' ALLOW FILTERING",
            profile="analytics",
        )
        return [dict(r) for r in rows][:500]
    return await _cached("q:fuera_serv", _q, ttl=300)


# ----------------------------------------------------------------------------
# 6. Modelos con más fallas
# ----------------------------------------------------------------------------
@router.get("/modelos-mas-fallas")
async def modelos_mas_fallas(_u: dict = Depends(current_user)):
    def _q():
        rows = cassandra_client.execute_raw(
            "SELECT tipo_medidor_id, estado FROM medidores", profile="analytics")
        c: dict[int, dict[str, int]] = defaultdict(lambda: {"total": 0, "fallas": 0})
        for r in rows:
            mid = r["tipo_medidor_id"]
            c[mid]["total"] += 1
            if not _es_activo(r["estado"]):
                c[mid]["fallas"] += 1
        return sorted(
            [{"modelo_id": k, **v, "tasa_falla": round(v["fallas"]/v["total"], 4) if v["total"] else 0}
             for k, v in c.items()],
            key=lambda x: -x["tasa_falla"],
        )
    return await _cached("q:modelos_fallas", _q, ttl=300)


# ----------------------------------------------------------------------------
# 7. Consumo por categoría tarifa y distrito
# ----------------------------------------------------------------------------
@router.get("/consumo-por-tarifa-distrito")
async def consumo_por_tarifa_distrito(_u: dict = Depends(current_user)):
    def _q():
        agg: dict[tuple[int, str], int] = defaultdict(int)
        rows = cassandra_client.execute_raw(
            "SELECT distrito_id, subcategoria, consumo_m3 FROM lecturas_por_zona_periodo",
            profile="analytics",
        )
        for r in rows:
            agg[(r["distrito_id"], r["subcategoria"] or "?")] += r["consumo_m3"] or 0
        return [
            {"distrito_id": d, "categoria": c, "consumo_m3": v}
            for (d, c), v in sorted(agg.items())
        ]
    return await _cached("q:consumo_tarifa_distrito", _q, ttl=180)


# ----------------------------------------------------------------------------
# 8. Zonas anómalas (top 20 por consumo)
# ----------------------------------------------------------------------------
@router.get("/zonas-anomalas")
async def zonas_anomalas(_u: dict = Depends(current_user)):
    def _q():
        agg: dict[tuple[int, str], int] = defaultdict(int)
        rows = cassandra_client.execute_raw(
            "SELECT distrito_id, zona, consumo_m3 FROM lecturas_por_zona_periodo",
            profile="analytics",
        )
        for r in rows:
            agg[(r["distrito_id"], r["zona"] or "?")] += r["consumo_m3"] or 0
        return sorted(
            [{"distrito_id": d, "zona": z, "consumo_m3": v} for (d, z), v in agg.items()],
            key=lambda x: -x["consumo_m3"],
        )[:20]
    return await _cached("q:zonas_anomalas", _q, ttl=180)


# ----------------------------------------------------------------------------
# 9. Lecturas fallidas (status >= 3)
# ----------------------------------------------------------------------------
@router.get("/lecturas-fallidas-mes")
async def lecturas_fallidas_mes(limite: int = 5000, _u: dict = Depends(current_user)):
    def _q():
        rows = cassandra_client.execute_raw(
            f"SELECT status FROM lecturas_por_medidor WHERE status >= 3 LIMIT {int(limite)} ALLOW FILTERING",
            profile="analytics",
        )
        c = Counter(r["status"] for r in rows)
        return {"total_fallidas": sum(c.values()), "por_status": dict(c)}
    return await _cached("q:lecturas_fallidas", _q, ttl=180)


# ----------------------------------------------------------------------------
# 10. Medidores con más de 4 años instalados
# ----------------------------------------------------------------------------
@router.get("/medidores-mas-4-anios")
async def medidores_mas_4_anios(_u: dict = Depends(current_user)):
    cutoff = date.today() - timedelta(days=365 * 4)
    def _q():
        rows = cassandra_client.execute_raw(
            "SELECT fecha_instalacion FROM medidores", profile="analytics")
        antiguos = 0
        for r in rows:
            f = r["fecha_instalacion"]
            if not f:
                continue
            # cassandra.util.Date → datetime.date
            if hasattr(f, "date"):
                f = f.date()
            elif not isinstance(f, date):
                try:
                    f = date.fromisoformat(str(f))
                except Exception:
                    continue
            if f < cutoff:
                antiguos += 1
        return {"total": antiguos, "cutoff": str(cutoff)}
    return await _cached(f"q:antiguos:{cutoff}", _q, ttl=600)


# ----------------------------------------------------------------------------
# 11. Per cápita residencial (m³ y litros/día ONU)
# ----------------------------------------------------------------------------
@router.get("/per-capita-residencial")
async def per_capita_residencial(_u: dict = Depends(current_user)):
    def _q():
        hab = {r["distrito_id"]: r["habitantes"]
               for r in cassandra_client.execute_raw("SELECT distrito_id, habitantes FROM distritos",
                                                      profile="analytics")}
        agg: dict[int, int] = defaultdict(int)
        for r in cassandra_client.execute_raw(
            "SELECT distrito_id, subcategoria, consumo_m3 FROM lecturas_por_zona_periodo",
            profile="analytics",
        ):
            if (r["subcategoria"] or "") in RESIDENCIALES:
                agg[r["distrito_id"]] += r["consumo_m3"] or 0
        out = []
        for d in sorted(agg):
            h = hab.get(d, 0)
            m3 = agg[d]
            # 3 meses de data → litros/día = m3*1000 / (90 días * habitantes)
            lpd = round(m3 * 1000 / (90 * h), 1) if h else 0
            out.append({"distrito_id": d, "consumo_m3": m3, "habitantes": h,
                        "litros_persona_dia": lpd, "nivel_onu": _nivel_onu(lpd)})
        return out
    return await _cached("q:percapita", _q, ttl=300)


def _nivel_onu(lpd: float) -> dict:
    """Clasifica litros/persona/día en los 6 niveles ONU."""
    escalas = [
        (100, 1, "Consumo ejemplar y consciente"),
        (180, 2, "Consumo responsable"),
        (250, 3, "Consumo moderado"),
        (300, 4, "Consumo elevado"),
        (400, 5, "Consumo inconsciente"),
        (float("inf"), 6, "Consumo crítico e insostenible"),
    ]
    for tope, nivel, label in escalas:
        if lpd <= tope:
            return {"nivel": nivel, "clasificacion": label}
    return {"nivel": 6, "clasificacion": "Consumo crítico e insostenible"}


# ----------------------------------------------------------------------------
# 12. Top 3 consumidores por distrito
# ----------------------------------------------------------------------------
@router.get("/top3-consumidores-distrito")
async def top3_consumidores_distrito(_u: dict = Depends(current_user)):
    def _q():
        agg: dict[tuple[int, str], int] = defaultdict(int)
        for r in cassandra_client.execute_raw(
            "SELECT distrito_id, mac, consumo_m3 FROM lecturas_por_zona_periodo",
            profile="analytics",
        ):
            agg[(r["distrito_id"], r["mac"])] += r["consumo_m3"] or 0
        por_distrito: dict[int, list[tuple[str, int]]] = defaultdict(list)
        for (d, m), v in agg.items():
            por_distrito[d].append((m, v))
        out = {}
        for d, items in por_distrito.items():
            items.sort(key=lambda x: -x[1])
            out[d] = [{"mac": m, "consumo_m3": v} for m, v in items[:3]]
        return out
    return await _cached("q:top3", _q, ttl=300)


# ----------------------------------------------------------------------------
# 13/14/15. Zonas renovación / errores / cobertura
# ----------------------------------------------------------------------------
@router.get("/zonas-renovacion")
async def zonas_renovacion(_u: dict = Depends(current_user)):
    def _q():
        rows = cassandra_client.execute_raw(
            "SELECT distrito_id, zona, estado FROM medidores", profile="analytics")
        zonas: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: {"total": 0, "falla": 0})
        for r in rows:
            key = (r["distrito_id"], r["zona"] or "?")
            zonas[key]["total"] += 1
            if not _es_activo(r["estado"]):
                zonas[key]["falla"] += 1
        return sorted(
            [{"distrito_id": d, "zona": z, **v,
              "tasa_falla": round(v["falla"]/v["total"], 3) if v["total"] else 0}
             for (d, z), v in zonas.items()],
            key=lambda x: -x["tasa_falla"],
        )[:30]
    return await _cached("q:renovacion", _q, ttl=300)


@router.get("/zonas-errores-por-distrito")
async def zonas_errores_por_distrito(distrito: int, _u: dict = Depends(current_user)):
    def _q():
        rows = cassandra_client.execute_raw(
            f"SELECT zona, estado FROM medidores WHERE distrito_id = {int(distrito)} ALLOW FILTERING",
            profile="analytics",
        )
        agg: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "fallas": 0})
        for r in rows:
            z = r["zona"] or "?"
            agg[z]["total"] += 1
            if not _es_activo(r["estado"]):
                agg[z]["fallas"] += 1
        return [{"zona": z, **v} for z, v in sorted(agg.items())]
    return await _cached(f"q:zonas_err:{distrito}", _q, ttl=300)


@router.get("/cobertura-antenas")
async def cobertura_antenas(_u: dict = Depends(current_user)):
    def _q():
        c: Counter[int] = Counter()
        for r in cassandra_client.execute_raw("SELECT gateway_id FROM medidores", profile="analytics"):
            if r["gateway_id"] is not None:
                c[r["gateway_id"]] += 1
        return [{"gateway_id": g, "medidores": n} for g, n in c.most_common()]
    return await _cached("q:cobertura", _q, ttl=300)


# ----------------------------------------------------------------------------
# 16. Proyección demanda (regresión lineal por periodo)
# ----------------------------------------------------------------------------
@router.get("/proyeccion-demanda-5anios")
async def proyeccion_demanda_5anios(_u: dict = Depends(current_user)):
    def _q():
        agg: dict[str, int] = defaultdict(int)
        for r in cassandra_client.execute_raw(
            "SELECT periodo, consumo_m3 FROM lecturas_por_zona_periodo", profile="analytics",
        ):
            agg[r["periodo"]] += r["consumo_m3"] or 0
        meses = sorted(agg.items())
        if len(meses) < 2:
            return {"historico_mensual_m3": meses, "proyeccion_5a_m3_mes": None}
        xs = list(range(len(meses)))
        ys = [v for _, v in meses]
        n = len(xs)
        sumx, sumy = sum(xs), sum(ys)
        sumxy = sum(x*y for x, y in zip(xs, ys))
        sumxx = sum(x*x for x in xs)
        denom = (n*sumxx - sumx*sumx) or 1
        slope = (n*sumxy - sumx*sumy) / denom
        intercept = (sumy - slope*sumx) / n
        proyec = intercept + slope*(n + 60)
        return {"historico_mensual_m3": meses, "proyeccion_5a_m3_mes": round(proyec, 2)}
    return await _cached("q:proyeccion5a", _q, ttl=600)


# ----------------------------------------------------------------------------
# 17. Impacto cambio tarifa
# ----------------------------------------------------------------------------
@router.get("/impacto-cambio-tarifa")
async def impacto_cambio_tarifa(desde: str, hacia: str, _u: dict = Depends(current_user)):
    def _q():
        n = sum(1 for r in cassandra_client.execute_raw(
            f"SELECT mac FROM medidores WHERE subcategoria='{desde}' ALLOW FILTERING",
            profile="analytics"))
        return {"medidores_afectados": n, "desde": desde, "hacia": hacia}
    return await _cached(f"q:impacto:{desde}:{hacia}", _q, ttl=300)


# ----------------------------------------------------------------------------
# 18. Medidores sin reporte
# ----------------------------------------------------------------------------
@router.get("/medidores-sin-reporte")
async def medidores_sin_reporte(_u: dict = Depends(current_user)):
    def _q():
        con_lectura = set()
        for r in cassandra_client.execute_raw(
            "SELECT mac FROM lecturas_por_zona_periodo", profile="analytics"):
            con_lectura.add(r["mac"])
        total = sum(1 for _ in cassandra_client.execute_raw("SELECT mac FROM medidores", profile="analytics"))
        return {"medidores_total": total, "con_lectura": len(con_lectura),
                "sin_reporte": total - len(con_lectura)}
    return await _cached("q:sin_reporte", _q, ttl=300)


# ----------------------------------------------------------------------------
# 19. Proyección ingresos del mes
# ----------------------------------------------------------------------------
@router.get("/proyeccion-ingresos-mes")
async def proyeccion_ingresos_mes(_u: dict = Depends(current_user)):
    def _q():
        c = Counter()
        for r in cassandra_client.execute_raw(
            "SELECT subcategoria, estado FROM medidores", profile="analytics"):
            if _es_activo(r["estado"]):
                c[r["subcategoria"] or "?"] += 1
        precios = {"R1": 1.4, "R2": 2.78, "R3": 5.21, "R4": 8.69, "C": 10.43,
                   "CE": 12.17, "I": 9.39, "P": 4.58, "S": 7.64}
        ingreso_usd = sum(c[k] * precios.get(k, 0) for k in c)
        return {"medidores_por_categoria": dict(c), "ingreso_mensual_usd_aprox": round(ingreso_usd, 2)}
    return await _cached("q:ingresos_mes", _q, ttl=600)


# ----------------------------------------------------------------------------
# 20/21. Consumo mínimo + ingresos en pies³
# ----------------------------------------------------------------------------
@router.get("/consumo-minimo-residencial")
async def consumo_minimo_residencial(_u: dict = Depends(current_user)):
    return {"minimo_m3": 12, "nota": "Cargo fijo de 12 m³/mes para residenciales"}


@router.get("/ingresos-pies3")
async def ingresos_pies3(_u: dict = Depends(current_user)):
    def _q():
        m3_total = 0
        for r in cassandra_client.execute_raw(
            "SELECT consumo_m3 FROM lecturas_por_zona_periodo", profile="analytics"):
            m3_total += r["consumo_m3"] or 0
        pies3 = m3_total * 35.3147
        return {"consumo_total_m3": m3_total, "consumo_pies3": round(pies3, 2)}
    return await _cached("q:pies3", _q, ttl=600)


# ----------------------------------------------------------------------------
# Consultas extra
# ----------------------------------------------------------------------------
@router.get("/distribucion-categorias")
async def distribucion_categorias(_u: dict = Depends(current_user)):
    def _q():
        c = Counter()
        for r in cassandra_client.execute_raw("SELECT subcategoria FROM medidores", profile="analytics"):
            c[r["subcategoria"] or "?"] += 1
        return dict(c)
    return await _cached("q:distribucion_cat", _q, ttl=600)


@router.get("/horas-pico")
async def horas_pico(limite: int = 20000, _u: dict = Depends(current_user)):
    """Consumo por hora del día (muestreo de lecturas)."""
    def _q():
        c: dict[int, int] = defaultdict(int)
        rows = cassandra_client.execute_raw(
            f"SELECT fecha_hora, consumo_m3 FROM lecturas_por_medidor LIMIT {int(limite)}",
            profile="analytics",
        )
        for r in rows:
            if r["fecha_hora"]:
                c[r["fecha_hora"].hour] += r["consumo_m3"] or 0
        return sorted([{"hora": h, "consumo_m3": v} for h, v in c.items()], key=lambda x: x["hora"])
    return await _cached("q:pico", _q, ttl=180)


@router.get("/medidores-por-modelo")
async def medidores_por_modelo(_u: dict = Depends(current_user)):
    def _q():
        c = Counter()
        for r in cassandra_client.execute_raw("SELECT tipo_medidor_id FROM medidores", profile="analytics"):
            c[r["tipo_medidor_id"]] += 1
        return [{"modelo_id": k, "medidores": v} for k, v in sorted(c.items(), key=lambda x: str(x[0]))]
    return await _cached("q:modelos_count", _q, ttl=600)


@router.get("/consumo-vs-clima")
async def consumo_vs_clima(
    start_date: str = Query("2026-02-01"),
    end_date: str = Query("2026-04-30"),
    _u: dict = Depends(current_user),
):
    """Correlación mensual: consumo total (m³) vs temperatura media y sequía (Open-Meteo)."""
    cache_key = f"q:clima:{start_date}:{end_date}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Consumo mensual desde lecturas
    consumo: dict[str, int] = defaultdict(int)
    for r in cassandra_client.execute_raw(
        "SELECT periodo, consumo_m3 FROM lecturas_por_zona_periodo", profile="analytics"):
        consumo[r["periodo"]] += r["consumo_m3"] or 0

    clima = await fetch_clima_mensual(start_date, end_date)

    periodos = sorted(set(consumo) | set(clima))
    serie = []
    for p in periodos:
        c = clima.get(p, {})
        serie.append({
            "periodo": p,
            "consumo_m3": consumo.get(p, 0),
            "temp_media": c.get("temp_media"),
            "precip_mm": c.get("precip_mm"),
            "sequia_indice": (c.get("sequia") or {}).get("indice"),
            "sequia_nivel": (c.get("sequia") or {}).get("nivel"),
        })
    payload = {"serie": serie, "fuente": "Open-Meteo (archive-api)"}
    await redis_client.set(cache_key, json.dumps(payload, default=str), ttl_seconds=1800)
    return payload


@router.get("/resumen-cobertura-poblacional")
async def resumen_cobertura_poblacional(_u: dict = Depends(current_user)):
    def _q():
        total = sum(r.get("habitantes") or 0
                    for r in cassandra_client.execute_raw("SELECT habitantes FROM distritos", profile="analytics"))
        n_med = sum(1 for _ in cassandra_client.execute_raw("SELECT mac FROM medidores", profile="analytics"))
        return {"poblacion_total": total, "medidores_total": n_med,
                "medidores_por_1000_hab": round(n_med * 1000 / total, 2) if total else 0}
    return await _cached("q:cobertura_pob", _q, ttl=600)
