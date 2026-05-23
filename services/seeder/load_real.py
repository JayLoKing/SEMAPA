"""SEMAPA — Loader de DATA REAL (CSV).

Carga los 4 CSV reales provistos en /data + catálogos en /data/seeds.
Modelo MAC-céntrico (ver infra/cassandra/init/02_tables.cql).

Orden (respeta dependencias de denormalización):
  1. Catálogos        (seeds/*.csv)
  2. infraestructuras → mapa catastro→(distrito,zona,lat,lon)
  3. contratos        → mapa mac→contrato, contrato_por_mac, contratos_por_ci
  4. medidores        → denormaliza contrato+infra, medidores_por_zona
  5. lecturas         → lecturas_por_medidor + lecturas_por_zona_periodo
  6. usuarios_sistema (auth)

Uso:
  docker compose run --rm seeder python load_real.py
"""
from __future__ import annotations

import csv
import json
import os
import time
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import bcrypt
from loguru import logger
from shapely.geometry import shape, Point

from cassandra_io import bulk_insert, connect


DATA_DIR = os.getenv("DATA_DIR", "/data")
SEEDS_DIR = os.getenv("SEEDS_DIR", "/data/seeds")
BATCH = int(os.getenv("LOAD_BATCH", "5000"))
CONCURRENCY = int(os.getenv("LOAD_CONCURRENCY", "150"))


# --------------------------------------------------------------------------
# Parsers tolerantes
# --------------------------------------------------------------------------
def _int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return default


def _dec(v, default=None):
    try:
        return Decimal(str(v).strip())
    except (InvalidOperation, ValueError, TypeError):
        return default


def _float(v, default=None):
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return default


def _date_iso(v):
    """yyyy-mm-dd → date | None."""
    v = (v or "").strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        return None


def _date_dmy(v):
    """dd/mm/yy → date | None (fecha_contrato)."""
    v = (v or "").strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%d/%m/%y").date()
    except ValueError:
        return None


def _ts_mdy(v):
    """MM/dd/yy HH:mm → datetime | None (lecturas / fecha_pago)."""
    v = (v or "").strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%m/%d/%y %H:%M")
    except ValueError:
        return None


def _fix_text(s):
    """Repara mojibake UTF-8 (AmÃ©rica→América) sin romper latin-1 crudo (Ñ)."""
    if not isinstance(s, str):
        return s
    try:
        # Si el str (leído como latin-1) era realmente UTF-8 mal interpretado,
        # este roundtrip lo arregla. Si no, lanza y devolvemos el original.
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def load_district_polygons():
    """Carga polígonos de distritos para corregir asignación por geografía."""
    path = f"{DATA_DIR}/distritos.geojson"
    if not os.path.exists(path):
        logger.warning(f"{path} no existe; sin corrección geográfica")
        return {}
    with open(path, encoding="utf-8") as f:
        gj = json.load(f)
    polys = {ft["properties"]["distrito"]: shape(ft["geometry"]) for ft in gj["features"]}
    logger.info(f"Polígonos cargados: {sorted(polys.keys())}")
    return polys


_POLYS: dict = {}


def real_distrito(lat, lon, fallback):
    """Devuelve el distrito real (point-in-polygon); cae a fallback si no se halla."""
    if lat is None or lon is None or not _POLYS:
        return fallback
    p = Point(lon, lat)
    for d, poly in _POLYS.items():
        if poly.contains(p):
            return d
    return fallback


def _rows(path):
    """Lee CSV con latin-1 (nunca falla) y repara mojibake por celda."""
    with open(path, newline="", encoding="latin-1") as f:
        for row in csv.DictReader(f):
            yield {k: _fix_text(v) for k, v in row.items()}


# --------------------------------------------------------------------------
# 1. Catálogos
# --------------------------------------------------------------------------
def load_catalogos(session):
    logger.info("Cargando catálogos...")

    ps = {
        "sub_alcaldias": session.prepare(
            "INSERT INTO sub_alcaldias (sub_alcaldia_id, nombre) VALUES (?, ?)"),
        "distritos": session.prepare(
            "INSERT INTO distritos (distrito_id, sub_alcaldia_id, nombre, habitantes) VALUES (?, ?, ?, ?)"),
        "zonas": session.prepare(
            "INSERT INTO zonas (distrito_id, zona_id, nombre, gateway_id, habitantes, total_medidores) "
            "VALUES (?, ?, ?, ?, ?, ?)"),
        "gateways": session.prepare(
            "INSERT INTO gateways (gateway_id, nombre, latitud, longitud) VALUES (?, ?, ?, ?)"),
        "modelos": session.prepare(
            "INSERT INTO modelos_medidor (modelo_id, marca, modelo, conectividad, aplicacion) "
            "VALUES (?, ?, ?, ?, ?)"),
        "tarifas": session.prepare(
            "INSERT INTO tarifas (categoria, alias, fijo_m3, usd_mes, r_13_25, r_26_50, r_51_75, "
            "r_76_100, r_101_150, r_mas_151, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"),
        "errores": session.prepare(
            "INSERT INTO errores_iot (codigo, descripcion) VALUES (?, ?)"),
        "tipos": session.prepare(
            "INSERT INTO tipos_infraestructura (tipo_id, descripcion) VALUES (?, ?)"),
    }

    for r in _rows(f"{SEEDS_DIR}/sub_alcaldias.csv"):
        session.execute(ps["sub_alcaldias"], (_int(r["sub_alcaldia_id"]), r["nombre"]))
    for r in _rows(f"{SEEDS_DIR}/distritos.csv"):
        session.execute(ps["distritos"], (
            _int(r["distrito_id"]), _int(r["sub_alcaldia_id"]), r["nombre"], _int(r["habitantes"])))
    for r in _rows(f"{SEEDS_DIR}/gateways.csv"):
        session.execute(ps["gateways"], (
            _int(r["gateway_id"]), r["nombre"], _float(r["latitud"]), _float(r["longitud"])))
    for r in _rows(f"{SEEDS_DIR}/modelos.csv"):
        session.execute(ps["modelos"], (
            _int(r["modelo_id"]), r["marca"], r["modelo"], r["conectividad"], r["aplicacion"]))
    for r in _rows(f"{SEEDS_DIR}/tarifas.csv"):
        session.execute(ps["tarifas"], (
            r["categoria"], r["alias"], _dec(r["fijo_m3"]), _dec(r["usd_mes"]),
            _dec(r["r_13_25"]), _dec(r["r_26_50"]), _dec(r["r_51_75"]), _dec(r["r_76_100"]),
            _dec(r["r_101_150"]), _dec(r["r_mas_151"]), r.get("descripcion", "")))
    for r in _rows(f"{SEEDS_DIR}/errores.csv"):
        session.execute(ps["errores"], (_int(r["codigo"]), r["descripcion"]))
    for r in _rows(f"{SEEDS_DIR}/tipos_infra.csv"):
        session.execute(ps["tipos"], (_int(r["tipo_id"]), r["descripcion"]))

    # Mapa (distrito_id, zona_nombre_upper) → gateway_id  (para denormalizar medidores)
    zona_gateway: dict[tuple[int, str], int] = {}
    for r in _rows(f"{SEEDS_DIR}/zonas.csv"):
        d = _int(r["distrito_id"])
        zid = _int(r["zona_id"])
        nombre = r["nombre"]
        gw = _int(r["gateway_id"])
        session.execute(ps["zonas"], (
            d, zid, nombre, gw, _int(r.get("habitantes")), _int(r.get("total_medidores"))))
        zona_gateway[(d, nombre.strip().upper())] = gw

    logger.success(f"Catálogos OK. zona→gateway entries={len(zona_gateway)}")
    return zona_gateway


# --------------------------------------------------------------------------
# 2. Infraestructuras
# --------------------------------------------------------------------------
def load_infraestructuras(session):
    logger.info("Cargando infraestructuras...")
    ps = session.prepare(
        "INSERT INTO infraestructuras (numero_catastro, propietario, ci, direccion, zona, "
        "distrito_id, manzano, lote, superficie_terreno, area_construida, uso_suelo, "
        "matricula_ddrr, valor_catastral, impuesto_anual, latitud, longitud) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")

    # catastro → (distrito_id, zona, lat, lon)  para denormalizar medidores
    infra_map: dict[str, tuple] = {}
    rows: list[tuple] = []
    n = 0
    corregidos = 0
    for r in _rows(f"{DATA_DIR}/infraestructuras.csv"):
        cat = r["numero_catastro"].strip()
        d_csv = _int(r["distrito"])
        zona = (r["zona"] or "").strip()
        lat = _float(r["latitud"])
        lon = _float(r["longitud"])
        d = real_distrito(lat, lon, d_csv)
        if d != d_csv:
            corregidos += 1
        infra_map[cat] = (d, zona, lat, lon)
        rows.append((
            cat, r["propietario"], r["ci"], r["direccion"], zona, d,
            _int(r["manzano"]), _int(r["lote"]), _int(r["superficie_terreno"]),
            _int(r["area_construida"]), r["uso_suelo"], r["matricula_ddrr"],
            _dec(r["valor_catastral"]), _dec(r["impuesto_anual"]), lat, lon))
        if len(rows) >= BATCH:
            n += bulk_insert(session, ps, rows, CONCURRENCY)
            rows.clear()
    if rows:
        n += bulk_insert(session, ps, rows, CONCURRENCY)
    logger.success(f"Infraestructuras: {n:,} | map={len(infra_map):,} | distritos corregidos por geografía: {corregidos:,}")
    return infra_map


# --------------------------------------------------------------------------
# 3. Contratos
# --------------------------------------------------------------------------
def load_contratos(session):
    logger.info("Cargando contratos...")
    ps_c = session.prepare(
        "INSERT INTO contratos (numero_contrato, numero_catastro, titular_contrato, ci_titular, "
        "categoria, subcategoria, medidor_iot, fecha_contrato, estado_contrato, diametro_conexion, "
        "tipo_servicio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    ps_mac = session.prepare(
        "INSERT INTO contrato_por_mac (medidor_iot, numero_contrato, numero_catastro, categoria, "
        "subcategoria, titular_contrato, ci_titular) VALUES (?, ?, ?, ?, ?, ?, ?)")
    ps_ci = session.prepare(
        "INSERT INTO contratos_por_ci (ci_titular, numero_contrato, medidor_iot) VALUES (?, ?, ?)")

    # mac → (contrato, catastro, categoria, subcat, titular, ci)  para denormalizar medidores
    mac_map: dict[str, tuple] = {}
    rc, rm, rci = [], [], []
    n = 0
    for r in _rows(f"{DATA_DIR}/contratos.csv"):
        nc = r["numero_contrato"].strip()
        cat = r["numero_catastro"].strip()
        mac = r["medidor_iot"].strip().upper()
        categoria = r["categoria"]
        subcat = r["subcategoria"]
        titular = r["titular_contrato"]
        ci = r["ci_titular"]
        mac_map[mac] = (nc, cat, categoria, subcat, titular, ci)
        rc.append((nc, cat, titular, ci, categoria, subcat, mac,
                   _date_dmy(r["fecha_contrato"]), r["estado_contrato"],
                   r["diametro_conexion"], r["tipo_servicio"]))
        rm.append((mac, nc, cat, categoria, subcat, titular, ci))
        rci.append((ci, nc, mac))
        if len(rc) >= BATCH:
            n += bulk_insert(session, ps_c, rc, CONCURRENCY)
            bulk_insert(session, ps_mac, rm, CONCURRENCY)
            bulk_insert(session, ps_ci, rci, CONCURRENCY)
            rc.clear(); rm.clear(); rci.clear()
    if rc:
        n += bulk_insert(session, ps_c, rc, CONCURRENCY)
        bulk_insert(session, ps_mac, rm, CONCURRENCY)
        bulk_insert(session, ps_ci, rci, CONCURRENCY)
    logger.success(f"Contratos: {n:,} | mac_map={len(mac_map):,}")
    return mac_map


# --------------------------------------------------------------------------
# 4. Medidores (denormaliza contrato + infra)
# --------------------------------------------------------------------------
def load_medidores(session, mac_map, infra_map, zona_gateway):
    logger.info("Cargando medidores (denormalizados)...")
    ps_m = session.prepare(
        "INSERT INTO medidores (mac, fecha_instalacion, fecha_desinstalacion, estado, tipo_medidor_id, "
        "numero_contrato, numero_catastro, categoria, subcategoria, zona, distrito_id, gateway_id, "
        "latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    ps_z = session.prepare(
        "INSERT INTO medidores_por_zona (distrito_id, zona, mac, numero_contrato, titular, categoria, "
        "subcategoria, estado, latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")

    rm, rz = [], []
    n = 0
    sin_contrato = 0
    for r in _rows(f"{DATA_DIR}/medidores.csv"):
        mac = r["medidor_iot"].strip().upper()
        estado = r["estado"]
        tipo = _int(r["tipo_medidor_id"])
        finst = _date_iso(r["fecha_instalacion"])
        fdes = _date_iso(r["fecha_desinstalacion"])

        nc = cat_num = categoria = subcat = titular = None
        d = zona = lat = lon = gw = None
        meta = mac_map.get(mac)
        if meta:
            nc, cat_num, categoria, subcat, titular, _ci = meta
            infra = infra_map.get(cat_num)
            if infra:
                d, zona, lat, lon = infra
                gw = zona_gateway.get((d, (zona or "").upper()))
        else:
            sin_contrato += 1

        rm.append((mac, finst, fdes, estado, tipo, nc, cat_num, categoria, subcat,
                   zona, d, gw, lat, lon))
        if d is not None and zona:
            rz.append((d, zona, mac, nc, titular, categoria, subcat, estado, lat, lon))

        if len(rm) >= BATCH:
            n += bulk_insert(session, ps_m, rm, CONCURRENCY)
            bulk_insert(session, ps_z, rz, CONCURRENCY)
            rm.clear(); rz.clear()
    if rm:
        n += bulk_insert(session, ps_m, rm, CONCURRENCY)
        bulk_insert(session, ps_z, rz, CONCURRENCY)
    logger.success(f"Medidores: {n:,} | sin contrato={sin_contrato:,}")


# --------------------------------------------------------------------------
# 5. Lecturas
# --------------------------------------------------------------------------
def load_lecturas(session, mac_map, infra_map):
    logger.info("Cargando lecturas...")
    ps_l = session.prepare(
        "INSERT INTO lecturas_por_medidor (mac, periodo, fecha_hora, lectura_anterior, lectura_actual, "
        "consumo_m3, radiobase, fecha_pago, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
    ps_zp = session.prepare(
        "INSERT INTO lecturas_por_zona_periodo (distrito_id, zona, periodo, mac, consumo_m3, "
        "subcategoria) VALUES (?, ?, ?, ?, ?, ?)")

    rl, rzp = [], []
    n = 0
    anomalias = 0
    for r in _rows(f"{DATA_DIR}/lecturas.csv"):
        mac = r["medidor_iot"].strip().upper()
        ts = _ts_mdy(r["fechaHoraLectura"])
        if ts is None:
            continue
        periodo = f"{ts.year:04d}-{ts.month:02d}"
        ant = _int(r["lecturaAnterior"])
        act = _int(r["LecturaActual"])
        consumo = act - ant
        radiobase = _int(r["radiobase"])
        fpago = _ts_mdy(r.get("fecha_pago"))

        status = 1
        if consumo < 0:
            status = 9          # anomalía: lectura decreciente
            anomalias += 1
        elif consumo > 5000:    # salto imposible (>5000 m³ en un periodo)
            status = 9
            anomalias += 1

        rl.append((mac, periodo, ts, ant, act, consumo, radiobase, fpago, status))

        meta = mac_map.get(mac)
        if meta:
            cat_num = meta[1]
            subcat = meta[3]
            infra = infra_map.get(cat_num)
            if infra:
                d, zona, _lat, _lon = infra
                if d is not None and zona:
                    rzp.append((d, zona, periodo, mac, consumo, subcat))

        if len(rl) >= BATCH:
            n += bulk_insert(session, ps_l, rl, CONCURRENCY)
            bulk_insert(session, ps_zp, rzp, CONCURRENCY)
            rl.clear(); rzp.clear()
    if rl:
        n += bulk_insert(session, ps_l, rl, CONCURRENCY)
        bulk_insert(session, ps_zp, rzp, CONCURRENCY)
    logger.success(f"Lecturas: {n:,} | anomalías status=9: {anomalias:,}")


# --------------------------------------------------------------------------
# 6. Usuarios sistema
# --------------------------------------------------------------------------
def load_usuarios(session):
    logger.info("Creando usuarios del sistema...")
    ps = session.prepare(
        "INSERT INTO usuarios_sistema (username, password_hash, rol, nombre, email, activo, "
        "fecha_creacion, ultimo_acceso) VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
    now = datetime.utcnow()
    users = [
        ("alcaldia", "alcaldia123", "ALCALDIA", "Alcaldía Municipal", "alcaldia@semapa.bo"),
        ("gerencia", "gerencia123", "GERENCIA", "Gerencia SEMAPA", "gerencia@semapa.bo"),
        ("contabilidad", "conta123", "CONTABILIDAD", "Contabilidad SEMAPA", "conta@semapa.bo"),
    ]
    for username, pwd, rol, nombre, email in users:
        h = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
        session.execute(ps, (username, h, rol, nombre, email, True, now, None))
    logger.success(f"Usuarios: {len(users)} (alcaldia/gerencia/contabilidad)")


# --------------------------------------------------------------------------
def main():
    t0 = time.time()
    global _POLYS
    _POLYS = load_district_polygons()
    cluster, session = connect()
    try:
        zona_gateway = load_catalogos(session)
        infra_map = load_infraestructuras(session)
        mac_map = load_contratos(session)
        load_medidores(session, mac_map, infra_map, zona_gateway)
        load_lecturas(session, mac_map, infra_map)
        load_usuarios(session)
        logger.success(f"Carga REAL completa en {time.time()-t0:.1f}s")
    finally:
        cluster.shutdown()


if __name__ == "__main__":
    main()
