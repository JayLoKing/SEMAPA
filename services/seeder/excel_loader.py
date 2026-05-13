"""Excel → estructuras tipadas para el seeder.

Lee Recursos_Practica_5.xlsx (montado vía volumen Docker en /recursos/recursos.xlsx)
y devuelve catálogos limpios: sub_alcaldias, distritos, zonas, gateways, modelos,
tarifas, errores, tipos de infraestructura, unidades educativas, infraestructuras
públicas.

Diseño:
- Lectura una sola vez con openpyxl (data_only=True para resolver fórmulas).
- Forward-fill manual de columnas jerárquicas (sub_alcaldia/distrito).
- Coordenadas DMS → decimales para gateways.
- Datos canonicalizados a int/Decimal/str (sin NaN sueltos).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import openpyxl
from loguru import logger


# ----- Sub-alcaldías (fijas, derivadas del Excel + enunciado) -----
SUB_ALCALDIAS: list[tuple[int, str]] = [
    (1, "TUNARI"),
    (2, "MOLLE"),
    (3, "ALEJO CALATAYUD"),
    (4, "VALLE HERMOSO"),
    (5, "ITOCTA"),
    (6, "ADELA ZAMUDIO"),
]
SUB_ALCALDIA_ID = {n.upper(): i for i, n in SUB_ALCALDIAS}

GATEWAY_NAME_TO_ID = {
    "LoRaWan-Teleferico": 1,
    "LoRaWan-ParqueVial": 2,
    "LoRaWan-ParqueLincon": 3,
    "LoRaWan-Petrolera": 4,
    # 5to gateway añadido para cubrir cobertura completa
    "LoRaWan-SurEste": 5,
}

GATEWAY_COORDS = {
    1: (-17.389222, -66.141722),  # Teleferico (17°23'21.2"S 66°08'30.2"W)
    2: (-17.381000, -66.153361),  # ParqueVial
    3: (-17.369861, -66.176389),  # ParqueLincon
    4: (-17.444083, -66.140694),  # Petrolera
    5: (-17.420000, -66.110000),  # SurEste (estimado)
}


@dataclass
class Distrito:
    distrito_id: int
    sub_alcaldia_id: int
    nombre: str
    habitantes: int = 0


@dataclass
class Zona:
    distrito_id: int
    zona_id: int
    nombre: str
    gateway_id: int
    habitantes: int  # cuota proporcional
    counts: dict[str, int] = field(default_factory=dict)  # categoría → cantidad
    centro_lat: float = -17.39
    centro_lon: float = -66.15

    @property
    def total_medidores(self) -> int:
        return sum(self.counts.values())


@dataclass
class ModeloMedidor:
    modelo_id: int
    marca: str
    modelo: str
    conectividad: str
    aplicacion: str


@dataclass
class TarifaCat:
    categoria: str
    alias: str
    fijo_m3: Decimal
    usd_mes: Decimal
    r_13_25: Decimal
    r_26_50: Decimal
    r_51_75: Decimal
    r_76_100: Decimal
    r_101_150: Decimal
    r_mas_151: Decimal
    descripcion: str


@dataclass
class TipoInfra:
    tipo_id: int
    descripcion: str


@dataclass
class UnidadEducativa:
    codigo: str
    nombre: str
    distrito_txt: str
    zona_txt: str
    direccion: str
    educacion: str


# Coordenadas aproximadas (centroide) por distrito de Cochabamba urbano.
DISTRITO_CENTROIDES: dict[int, tuple[float, float]] = {
    1: (-17.378, -66.150),
    2: (-17.395, -66.155),
    3: (-17.401, -66.160),
    4: (-17.405, -66.140),
    5: (-17.412, -66.142),
    6: (-17.418, -66.158),
    7: (-17.423, -66.165),
    8: (-17.430, -66.155),
    9: (-17.438, -66.148),
    10: (-17.445, -66.130),
    11: (-17.452, -66.140),
    12: (-17.395, -66.180),
    13: (-17.410, -66.190),
    14: (-17.420, -66.200),
    15: (-17.460, -66.170),
}


def _parse_dms(dms: str) -> float | None:
    m = re.match(r"(\d+)°(\d+)'(\d+\.?\d*)\"([NSEW])", dms.strip())
    if not m:
        return None
    deg, mn, sec, hemi = m.groups()
    val = int(deg) + int(mn) / 60 + float(sec) / 3600
    if hemi in ("S", "W"):
        val = -val
    return val


def _as_int(x) -> int | None:
    if x is None:
        return None
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def load_workbook(path: str | Path) -> openpyxl.Workbook:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Excel no encontrado: {p}")
    logger.info(f"Cargando Excel: {p}")
    return openpyxl.load_workbook(p, data_only=True, read_only=False)


def load_distritos_zonas(wb: openpyxl.Workbook) -> tuple[list[Distrito], list[Zona]]:
    """Lee la hoja 'Distritos' aplicando forward-fill jerárquico.

    Estructura observada (fila 2 = header):
      col A: sub-alcaldía (texto)  → forward-fill
      col B: distrito_id (float)   → forward-fill
      col C: zona_id (sub-distrito, float)
      col D: zona_nombre (texto)
      col E: gateway (texto)
      col F: habitantes del distrito (solo en la primera fila del distrito)
      cols G..O: R1, R2, R3, R4, C, CE, I, P, S
      col P: Total medidores
    """
    ws = wb["Distritos"]
    distritos: dict[int, Distrito] = {}
    zonas: list[Zona] = []

    cur_sub = None
    cur_dist = None

    for row_idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        if row is None or all(c is None for c in row):
            continue
        sub_txt, dist_id, zona_id, zona_nom, gw_name, hab, r1, r2, r3, r4, c, ce, i, p, s, total = row[:16]

        if sub_txt:
            cur_sub = str(sub_txt).strip().upper()
        if dist_id is not None:
            cur_dist = _as_int(dist_id)
            if cur_dist not in distritos and cur_dist is not None and cur_sub:
                distritos[cur_dist] = Distrito(
                    distrito_id=cur_dist,
                    sub_alcaldia_id=SUB_ALCALDIA_ID.get(cur_sub, 1),
                    nombre=f"DISTRITO {cur_dist}",
                    habitantes=_as_int(hab) or 0,
                )
        if hab and cur_dist in distritos and distritos[cur_dist].habitantes == 0:
            distritos[cur_dist].habitantes = _as_int(hab) or 0

        zid = _as_int(zona_id)
        if zid is None or not zona_nom or cur_dist is None:
            continue

        counts = {
            "R1": _as_int(r1) or 0,
            "R2": _as_int(r2) or 0,
            "R3": _as_int(r3) or 0,
            "R4": _as_int(r4) or 0,
            "C": _as_int(c) or 0,
            "CE": _as_int(ce) or 0,
            "I": _as_int(i) or 0,
            "P": _as_int(p) or 0,
            "S": _as_int(s) or 0,
        }
        gw_id = GATEWAY_NAME_TO_ID.get(str(gw_name).strip() if gw_name else "", 1)
        centro = DISTRITO_CENTROIDES.get(cur_dist, (-17.39, -66.15))

        zonas.append(
            Zona(
                distrito_id=cur_dist,
                zona_id=zid,
                nombre=str(zona_nom).strip(),
                gateway_id=gw_id,
                habitantes=0,  # se reparte después
                counts=counts,
                centro_lat=centro[0],
                centro_lon=centro[1],
            )
        )

    # Reparto de habitantes del distrito por zona en proporción a Total medidores
    for dist in distritos.values():
        zonas_d = [z for z in zonas if z.distrito_id == dist.distrito_id]
        total = sum(z.total_medidores for z in zonas_d) or 1
        for z in zonas_d:
            z.habitantes = int(dist.habitantes * z.total_medidores / total)

    logger.info(f"Distritos cargados: {len(distritos)} | Zonas: {len(zonas)}")
    return list(distritos.values()), zonas


def load_tarifas(wb: openpyxl.Workbook) -> list[TarifaCat]:
    ws = wb["Tarifario"]
    rows = list(ws.iter_rows(min_row=3, max_row=12, values_only=True))
    out: list[TarifaCat] = []
    cur_alias = None
    for row in rows:
        if row is None or all(c is None for c in row):
            continue
        alias_txt, cat, fijo, usd, r1, r2, r3, r4, r5, r6, desc = row[:11]
        if alias_txt:
            cur_alias = str(alias_txt).strip()
        if not cat:
            continue
        out.append(
            TarifaCat(
                categoria=str(cat).strip().upper(),
                alias=cur_alias or "",
                fijo_m3=Decimal(str(fijo or 0)),
                usd_mes=Decimal(str(usd or 0)),
                r_13_25=Decimal(str(r1 or 0)),
                r_26_50=Decimal(str(r2 or 0)),
                r_51_75=Decimal(str(r3 or 0)),
                r_76_100=Decimal(str(r4 or 0)),
                r_101_150=Decimal(str(r5 or 0)),
                r_mas_151=Decimal(str(r6 or 0)),
                descripcion=str(desc or "").strip(),
            )
        )
    # Garantizar las 9 categorías
    needed = {"R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"}
    found = {t.categoria for t in out}
    missing = needed - found
    if missing:
        logger.warning(f"Tarifas faltantes en Excel: {missing}. Se añadirán fallback.")
        fallbacks = {
            "S": TarifaCat("S", "Social", Decimal("8"), Decimal("0.67"), Decimal("0.5"),
                           Decimal("0.6"), Decimal("0.7"), Decimal("0.8"), Decimal("0.9"),
                           Decimal("1.0"), "Tarifa social, predios estatales con fines sociales"),
        }
        for m in missing:
            if m in fallbacks:
                out.append(fallbacks[m])
    logger.info(f"Tarifas: {len(out)} categorías")
    return out


def load_modelos(wb: openpyxl.Workbook) -> list[ModeloMedidor]:
    ws = wb["ModeloMedidores"]
    out: list[ModeloMedidor] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        tid, marca, modelo, conect, app, _ = row[:6]
        mid = _as_int(tid)
        if mid is None:
            continue
        out.append(
            ModeloMedidor(
                modelo_id=mid,
                marca=str(marca or "").strip(),
                modelo=str(modelo or "").strip(),
                conectividad=str(conect or "").strip(),
                aplicacion=str(app or "").strip(),
            )
        )
    logger.info(f"Modelos medidor: {len(out)}")
    return out


def load_errores(wb: openpyxl.Workbook) -> list[tuple[int, str]]:
    ws = wb["ErroresIOT"]
    out: list[tuple[int, str]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        code = _as_int(row[0])
        if code is None:
            continue
        out.append((code, str(row[1] or "").strip()))
    logger.info(f"Errores IoT: {len(out)}")
    return out


def load_tipos_infra(wb: openpyxl.Workbook) -> list[TipoInfra]:
    ws = wb["Infraestructuras"]
    out: list[TipoInfra] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        tid = _as_int(row[0])
        if tid is None:
            continue
        out.append(TipoInfra(tipo_id=tid, descripcion=str(row[1] or "").strip()))
    logger.info(f"Tipos infraestructura: {len(out)}")
    return out


def load_unidades_educativas(wb: openpyxl.Workbook) -> list[UnidadEducativa]:
    ws = wb["UnidadesEducativas"]
    out: list[UnidadEducativa] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[1] is None:
            continue
        out.append(
            UnidadEducativa(
                codigo=str(row[1]),
                nombre=str(row[2] or "").strip(),
                distrito_txt=str(row[0] or "").strip(),
                zona_txt=str(row[7] or "").strip(),
                direccion=str(row[8] or "").strip(),
                educacion=str(row[3] or "").strip(),
            )
        )
    logger.info(f"Unidades educativas: {len(out)}")
    return out


def gateways() -> list[tuple[int, str, float, float]]:
    out = []
    for name, gid in GATEWAY_NAME_TO_ID.items():
        lat, lon = GATEWAY_COORDS[gid]
        out.append((gid, name, lat, lon))
    return out
