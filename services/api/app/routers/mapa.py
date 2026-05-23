"""Mapa interactivo: drill-down distrito → medidores → info completa."""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.cassandra_client import cassandra_client
from app.core.redis_client import redis_client
from app.core.security import current_user


router = APIRouter()

ESTADOS_ACTIVOS = {"Operativo", "Reacondicionado", "Nuevo"}


def _val(v: Any) -> Any:
    if hasattr(v, "hex"):
        return str(v)
    if isinstance(v, Decimal):
        return str(v)
    return v


@router.get("/distritos")
async def distritos(_u: dict = Depends(current_user)):
    """Lista distritos con totales (para choropleth del mapa)."""
    cache = await redis_client.get("mapa:distritos")
    if cache:
        return json.loads(cache)

    distros = {}
    for r in cassandra_client.execute_raw(
        "SELECT distrito_id, nombre, habitantes, sub_alcaldia_id FROM distritos", profile="analytics"):
        distros[r["distrito_id"]] = {
            "distrito_id": r["distrito_id"], "nombre": r["nombre"],
            "habitantes": r["habitantes"] or 0, "sub_alcaldia_id": r["sub_alcaldia_id"],
            "medidores": 0, "consumo_m3": 0,
        }

    for r in cassandra_client.execute_raw("SELECT distrito_id FROM medidores", profile="analytics"):
        d = r["distrito_id"]
        if d in distros:
            distros[d]["medidores"] += 1

    for r in cassandra_client.execute_raw(
        "SELECT distrito_id, consumo_m3 FROM lecturas_por_zona_periodo", profile="analytics"):
        d = r["distrito_id"]
        if d in distros:
            distros[d]["consumo_m3"] += r["consumo_m3"] or 0

    out = sorted(distros.values(), key=lambda x: x["distrito_id"])
    await redis_client.set("mapa:distritos", json.dumps(out, default=str), ttl_seconds=300)
    return out


@router.get("/distritos-geo")
async def distritos_geo(_u: dict = Depends(current_user)):
    """Bounding box + centroide por distrito (de coords reales de medidores).

    Permite dibujar polígonos delimitados y hacer zoom (fitBounds) en el mapa.
    """
    cache = await redis_client.get("mapa:distritos_geo")
    if cache:
        return json.loads(cache)

    nombres = {}
    for r in cassandra_client.execute_raw("SELECT distrito_id, nombre FROM distritos", profile="analytics"):
        nombres[r["distrito_id"]] = r["nombre"]

    agg: dict[int, dict] = {}
    for r in cassandra_client.execute_raw(
        "SELECT distrito_id, latitud, longitud FROM medidores", profile="analytics"):
        d = r["distrito_id"]
        lat, lon = r.get("latitud"), r.get("longitud")
        if d is None or lat is None or lon is None:
            continue
        a = agg.setdefault(d, {"min_lat": lat, "max_lat": lat, "min_lon": lon,
                               "max_lon": lon, "sum_lat": 0.0, "sum_lon": 0.0, "n": 0})
        a["min_lat"] = min(a["min_lat"], lat); a["max_lat"] = max(a["max_lat"], lat)
        a["min_lon"] = min(a["min_lon"], lon); a["max_lon"] = max(a["max_lon"], lon)
        a["sum_lat"] += lat; a["sum_lon"] += lon; a["n"] += 1

    consumo: dict[int, int] = {}
    for r in cassandra_client.execute_raw(
        "SELECT distrito_id, consumo_m3 FROM lecturas_por_zona_periodo", profile="analytics"):
        consumo[r["distrito_id"]] = consumo.get(r["distrito_id"], 0) + (r["consumo_m3"] or 0)

    out = []
    for d, a in sorted(agg.items()):
        if a["n"] == 0:
            continue
        out.append({
            "distrito_id": d,
            "nombre": nombres.get(d, f"Distrito {d}"),
            "medidores": a["n"],
            "consumo_m3": consumo.get(d, 0),
            "bbox": [[a["min_lat"], a["min_lon"]], [a["max_lat"], a["max_lon"]]],
            "centroid": [a["sum_lat"] / a["n"], a["sum_lon"] / a["n"]],
        })
    await redis_client.set("mapa:distritos_geo", json.dumps(out, default=str), ttl_seconds=600)
    return out


def _uso_suelo_for_catastro_cache():
    """Devuelve dict {numero_catastro: uso_suelo} para filtrar medidores.

    Cache 5min. Costo: 1 scan completo de infraestructuras.
    """
    return None  # placeholder — usamos cache Redis abajo


async def _load_uso_suelo_map() -> dict[str, str]:
    cache = await redis_client.get("mapa:catastro_uso_suelo")
    if cache:
        return json.loads(cache)
    m: dict[str, str] = {}
    for r in cassandra_client.execute_raw(
        "SELECT numero_catastro, uso_suelo FROM infraestructuras", profile="analytics"):
        if r.get("numero_catastro"):
            m[r["numero_catastro"]] = (r.get("uso_suelo") or "").strip()
    await redis_client.set("mapa:catastro_uso_suelo", json.dumps(m), ttl_seconds=600)
    return m


@router.get("/usos-suelo")
async def usos_suelo(_u: dict = Depends(current_user)):
    """Catálogo distinct de uso_suelo (para combobox del filtro)."""
    cache = await redis_client.get("mapa:usos_suelo")
    if cache:
        return json.loads(cache)
    vals: set[str] = set()
    for r in cassandra_client.execute_raw(
        "SELECT uso_suelo FROM infraestructuras", profile="analytics"):
        u = (r.get("uso_suelo") or "").strip()
        if u:
            vals.add(u)
    out = sorted(vals)
    await redis_client.set("mapa:usos_suelo", json.dumps(out), ttl_seconds=900)
    return out


@router.get("/distrito/{distrito_id}/zonas")
async def zonas_distrito(distrito_id: int, _u: dict = Depends(current_user)):
    """Lista zonas de un distrito con count de medidores + consumo total."""
    cache_key = f"mapa:zonas_distrito:{distrito_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    rows = list(cassandra_client.execute("medidores_por_zona", (distrito_id,)))
    agg: dict[str, dict] = {}
    for r in rows:
        z = (r.get("zona") or "").strip()
        if not z:
            continue
        a = agg.setdefault(z, {"zona": z, "medidores": 0, "consumo_m3": 0})
        a["medidores"] += 1

    # Consumo por zona
    for r in cassandra_client.execute_raw(
        f"SELECT zona, consumo_m3 FROM lecturas_por_zona_periodo WHERE distrito_id={int(distrito_id)} ALLOW FILTERING",
        profile="analytics"):
        z = (r.get("zona") or "").strip()
        if z in agg:
            agg[z]["consumo_m3"] += r.get("consumo_m3") or 0

    out = sorted(agg.values(), key=lambda x: -x["medidores"])
    await redis_client.set(cache_key, json.dumps(out), ttl_seconds=300)
    return out


@router.get("/distrito/{distrito_id}/medidores")
async def medidores_distrito(
    distrito_id: int,
    zona: str | None = Query(None, description="Filtrar por zona exacta"),
    uso_suelo: str | None = Query(None, description="Filtrar por uso de suelo"),
    limite: int = Query(2000, ge=1, le=20000),
    _u: dict = Depends(current_user),
):
    """Medidores de un distrito (opcionalmente filtrados por zona + uso_suelo)."""
    rows = list(cassandra_client.execute("medidores_por_zona", (distrito_id,)))

    uso_map: dict[str, str] = {}
    mac_catastro: dict[str, str] = {}
    if uso_suelo:
        uso_map = await _load_uso_suelo_map()
        # Build mac → catastro map for this distrito (single scan)
        cache_key = f"mapa:mac_catastro:{distrito_id}"
        cached = await redis_client.get(cache_key)
        if cached:
            mac_catastro = json.loads(cached)
        else:
            for r in cassandra_client.execute_raw(
                f"SELECT mac, numero_catastro FROM medidores WHERE distrito_id={int(distrito_id)} ALLOW FILTERING",
                profile="analytics"):
                if r.get("mac") and r.get("numero_catastro"):
                    mac_catastro[r["mac"]] = r["numero_catastro"]
            await redis_client.set(cache_key, json.dumps(mac_catastro), ttl_seconds=600)

    out = []
    for r in rows:
        if r.get("latitud") is None or r.get("longitud") is None:
            continue
        if zona and (r.get("zona") or "").strip() != zona.strip():
            continue
        if uso_suelo:
            cat = mac_catastro.get(r["mac"])
            if not cat or uso_map.get(cat, "") != uso_suelo:
                continue
        out.append({
            "mac": r["mac"],
            "numero_contrato": r.get("numero_contrato"),
            "titular": r.get("titular"),
            "categoria": r.get("categoria"),
            "subcategoria": r.get("subcategoria"),
            "estado": r.get("estado"),
            "activo": r.get("estado") in ESTADOS_ACTIVOS,
            "zona": r.get("zona"),
            "lat": r["latitud"],
            "lon": r["longitud"],
        })
        if len(out) >= limite:
            break
    return {"distrito_id": distrito_id, "zona": zona, "uso_suelo": uso_suelo,
            "total": len(out), "medidores": out}


@router.get("/zona/{distrito_id}/{zona}/medidores")
async def medidores_zona(
    distrito_id: int,
    zona: str,
    uso_suelo: str | None = Query(None),
    limite: int = Query(3000, ge=1, le=10000),
    _u: dict = Depends(current_user),
):
    """Atajo: medidores de una zona específica (con filtro uso_suelo opcional)."""
    return await medidores_distrito(distrito_id, zona, uso_suelo, limite, _u)


@router.get("/medidor/{mac}")
async def medidor_detalle(mac: str, _u: dict = Depends(current_user)):
    """Info completa de un medidor: contrato, persona, infra, consumo."""
    mac = mac.upper()
    med = list(cassandra_client.execute("medidor_get", (mac,)))
    if not med:
        raise HTTPException(404, "Medidor no encontrado")
    m = med[0]

    contrato = None
    cm = list(cassandra_client.execute("contrato_por_mac", (mac,)))
    if cm:
        nc = cm[0]["numero_contrato"]
        full = list(cassandra_client.execute("contrato_get", (nc,)))
        contrato = {k: _val(v) for k, v in full[0].items()} if full else {k: _val(v) for k, v in cm[0].items()}

    infra = None
    if m.get("numero_catastro"):
        irows = list(cassandra_client.execute("infra_get", (m["numero_catastro"],)))
        if irows:
            infra = {k: _val(v) for k, v in irows[0].items()}

    lecturas = []
    for r in cassandra_client.execute("lecturas_de_medidor", (mac, 12)):
        lecturas.append({
            "periodo": r.get("periodo"),
            "consumo_m3": r.get("consumo_m3"),
            "lectura_actual": r.get("lectura_actual"),
            "fecha_hora": _val(r.get("fecha_hora")),
            "pagado": r.get("fecha_pago") is not None,
        })

    return {
        "medidor": {k: _val(v) for k, v in m.items()},
        "contrato": contrato,
        "infraestructura": infra,
        "lecturas": lecturas,
    }
