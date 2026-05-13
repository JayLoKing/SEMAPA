"""SEMAPA — Servicio de cálculo de tarifas.

Implementa el "Reglamento Interno sobre Política Tarifaria SEMAPA" (07-sep-2004),
Capítulos I..XVIII, Arts. 1..28.

Núcleo:
    - 9 categorías (R1, R2, R3, R4, C, CE, I, P, S)
    - Cargo fijo: primeros 12 m³/mes (independiente del consumo)
    - Tramos progresivos por m³: 13-25, 26-50, 51-75, 76-100, 101-150, >151

Reglas especiales (Capítulos II..XVI) se modelan como funciones puras de
clasificación y descargas industriales/de alcantarillado.

Precios en USD; conversión a Bs con `tipo_cambio` (USD→Bs).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Literal


Categoria = Literal["R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"]

CATEGORIAS_VALIDAS: tuple[str, ...] = ("R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S")

# Cargo fijo de los primeros 12 m³/mes (USD).
M3_FIJO = 12

# Tramos progresivos: (limite_superior_m3, índice de precio).
# El sexto tramo (>=151) no tiene límite superior → None.
TRAMOS = [
    (25, "r_13_25"),
    (50, "r_26_50"),
    (75, "r_51_75"),
    (100, "r_76_100"),
    (150, "r_101_150"),
    (None, "r_mas_151"),
]

# Factor K (Arts. 14 y 16).
FACTOR_K: dict[str, Decimal] = {
    "K1": Decimal("1.00"),
    "K2": Decimal("1.10"),
    "K3": Decimal("1.20"),
    "K4": Decimal("1.33"),
    "K5": Decimal("1.45"),
}

# Cargos fijos por descarga industrial / alcantarillado (m³).
DESCARGA_FIJA_M3 = {
    "MATADERO": 600,            # Art. 15
    "TERMINAL": 1200,           # Art. 21
    "BALNEARIO": 480,           # Art. 22
    "BANO_PUBLICO": 180,        # Art. 24
    "LAVANDERIA": 120,          # Art. 13
    "ESTACION_SERVICIO": 240,   # Art. 10
    "HIPERMERCADO": 400,        # Art. 7.3
    "LAVADERO_JEANS": 65,       # Art. 14 (equiv 65 m³ → Bs 204)
}

# Descarga industrial Art. 16 (curtiembres / metalmecánicas) — Bs.
ART16_RANGOS_BS = [
    (70, Decimal("218.50")),
    (150, Decimal("470.00")),
    (300, Decimal("1004.00")),
]
ART16_INCREMENTO_PCT = Decimal("0.30")
ART14_DESCARGA_FIJA_BS = Decimal("204.00")
ART16_MULTA_K10_BS = Decimal("5000.00")


@dataclass
class TarifaCategoria:
    """Tabla de precios para una categoría, todo en USD."""
    categoria: str
    fijo_m3: Decimal           # USD por los primeros 12 m³/mes (cargo fijo)
    usd_mes: Decimal           # alias informativo (== fijo_m3 / 12 normalmente)
    r_13_25: Decimal           # USD/m³ tramo 2
    r_26_50: Decimal
    r_51_75: Decimal
    r_76_100: Decimal
    r_101_150: Decimal
    r_mas_151: Decimal


@dataclass
class DesgloseTramo:
    desde_m3: int
    hasta_m3: int
    m3_facturados: int
    precio_usd_m3: Decimal
    subtotal_usd: Decimal


@dataclass
class Factura:
    categoria: str
    consumo_m3: Decimal
    monto_usd: Decimal
    monto_bs: Decimal
    tipo_cambio: Decimal
    tramos: list[DesgloseTramo] = field(default_factory=list)
    cargos_extra: list[tuple[str, Decimal, Decimal]] = field(default_factory=list)
    # (concepto, monto_usd, monto_bs)

    def to_dict(self) -> dict:
        return {
            "categoria": self.categoria,
            "consumo_m3": str(self.consumo_m3),
            "monto_usd": str(self.monto_usd),
            "monto_bs": str(self.monto_bs),
            "tipo_cambio": str(self.tipo_cambio),
            "tramos": [
                {
                    "desde_m3": t.desde_m3,
                    "hasta_m3": t.hasta_m3,
                    "m3_facturados": t.m3_facturados,
                    "precio_usd_m3": str(t.precio_usd_m3),
                    "subtotal_usd": str(t.subtotal_usd),
                }
                for t in self.tramos
            ],
            "cargos_extra": [
                {"concepto": c, "usd": str(u), "bs": str(b)}
                for c, u, b in self.cargos_extra
            ],
        }


def _q(x: Decimal, places: str = "0.01") -> Decimal:
    return x.quantize(Decimal(places), rounding=ROUND_HALF_UP)


# =============================================================================
# Núcleo: cálculo por tramos
# =============================================================================

def calcular_consumo(tarifa: TarifaCategoria, consumo_m3: int | Decimal) -> tuple[Decimal, list[DesgloseTramo]]:
    """Devuelve (subtotal_usd, desglose por tramo). Cargo fijo + tramos progresivos."""
    consumo = int(Decimal(consumo_m3))
    desglose: list[DesgloseTramo] = []
    subtotal = Decimal("0")

    # Cargo fijo: primeros 12 m³, siempre se cobra completo.
    desglose.append(DesgloseTramo(
        desde_m3=0,
        hasta_m3=M3_FIJO,
        m3_facturados=M3_FIJO,
        precio_usd_m3=Decimal("0"),
        subtotal_usd=tarifa.fijo_m3,
    ))
    subtotal += tarifa.fijo_m3

    if consumo <= M3_FIJO:
        return subtotal, desglose

    restantes = consumo - M3_FIJO
    desde = M3_FIJO
    for limite, attr in TRAMOS:
        precio = getattr(tarifa, attr)
        if limite is None:
            m3_tramo = restantes
            hasta = desde + m3_tramo
        else:
            m3_tramo = min(restantes, limite - desde)
            hasta = desde + m3_tramo
        if m3_tramo <= 0:
            desde = limite or desde
            continue
        sub = Decimal(m3_tramo) * precio
        desglose.append(DesgloseTramo(
            desde_m3=desde + 1,
            hasta_m3=hasta,
            m3_facturados=m3_tramo,
            precio_usd_m3=precio,
            subtotal_usd=sub,
        ))
        subtotal += sub
        restantes -= m3_tramo
        desde = hasta
        if restantes <= 0:
            break
    return subtotal, desglose


# =============================================================================
# Helpers de descarga industrial (Arts. 13–16, 21, 22, 24)
# =============================================================================

def descarga_alcantarillado_fija_usd(
    tarifa_ce: TarifaCategoria, m3_fijos: int
) -> Decimal:
    """Descarga industrial cobrada como `m3_fijos` m³ en categoría CE."""
    sub, _ = calcular_consumo(tarifa_ce, m3_fijos)
    # No cargo fijo extra (ya incluido); restamos primeros 12 m³ si fijos < 12 ya cubre.
    return sub


def descarga_art16_bs(volumen_m3: int, factor_k: str) -> Decimal:
    """Art. 16 (curtiembres/metalmecánicas) — descarga industrial Bs."""
    if factor_k not in FACTOR_K:
        raise ValueError(f"factor_k inválido: {factor_k}")
    base: Decimal
    if volumen_m3 <= 70:
        base = ART16_RANGOS_BS[0][1]
    elif volumen_m3 <= 150:
        base = ART16_RANGOS_BS[1][1]
    elif volumen_m3 <= 300:
        base = ART16_RANGOS_BS[2][1]
    else:
        extra_bloques = (volumen_m3 - 300 + 99) // 100   # cada 100 m³ extras
        base = ART16_RANGOS_BS[2][1] * (Decimal("1") + ART16_INCREMENTO_PCT * Decimal(extra_bloques))
    return _q(base * FACTOR_K[factor_k])


def descarga_art14_bs(factor_k: str) -> Decimal:
    """Art. 14 — descarga industrial lavadero de jeans (Bs 204 × K)."""
    return _q(ART14_DESCARGA_FIJA_BS * FACTOR_K[factor_k])


# =============================================================================
# Clasificadores (Art. 6, 7, 9, 10, 17, 18, 20)
# =============================================================================

def clasificar_edificio(tipo: Literal["DEPARTAMENTOS", "MIXTO", "CONDOMINIO", "GALERIA"]) -> Categoria:
    """Art. 6."""
    return {
        "DEPARTAMENTOS": "R3",
        "MIXTO": "R4",
        "CONDOMINIO": "R4",
        "GALERIA": "C",
    }[tipo]


def clasificar_supermercado(tipo: Literal["MINI", "SUPER", "HIPER"]) -> Categoria:
    """Art. 7."""
    return {"MINI": "R4", "SUPER": "C", "HIPER": "CE"}[tipo]


def clasificar_hospedaje(estrellas: int, sub_tipo: str = "HOTEL") -> Categoria:
    """Art. 9. sub_tipo ∈ {HOTEL, APART, CASA_HUESPED, ALOJAMIENTO, RESIDENCIAL, MOTEL}."""
    if sub_tipo.upper() == "MOTEL":
        return "CE"
    if sub_tipo.upper() in {"APART", "CASA_HUESPED", "ALOJAMIENTO", "RESIDENCIAL"}:
        return "C"
    return "C" if estrellas <= 3 else "CE"


def clasificar_estacion_servicio(con_lavadero: bool) -> Categoria:
    """Art. 10."""
    return "CE" if con_lavadero else "C"


def clasificar_restaurante(superficie_m2: float) -> Categoria:
    """Art. 17."""
    if superficie_m2 <= 40:
        return "R4"
    if superficie_m2 <= 100:
        return "C"
    return "CE"


def clasificar_hospital(estatal: bool) -> Categoria:
    """Art. 18."""
    return "P" if estatal else "CE"


def clasificar_centro_educativo(privado: bool) -> Categoria:
    """Art. 20. Centros estatales = P; privados = CE."""
    return "CE" if privado else "P"


# =============================================================================
# Servicio principal
# =============================================================================

class TarifaService:
    """Calcula facturación mensual.

    Uso:
        svc = TarifaService(tarifas={"R3": TarifaCategoria(...), ...})
        factura = svc.facturar("R3", consumo_m3=Decimal("35"), tipo_cambio=Decimal("6.96"))
    """

    def __init__(self, tarifas: dict[str, TarifaCategoria]):
        faltantes = set(CATEGORIAS_VALIDAS) - set(tarifas)
        if faltantes:
            raise ValueError(f"Faltan tarifas para categorías: {faltantes}")
        self.tarifas = tarifas

    # --------------------------------------------------------------------- #
    def facturar(
        self,
        categoria: Categoria,
        consumo_m3: int | Decimal,
        tipo_cambio: Decimal,
        cargos_extra_usd: Iterable[tuple[str, Decimal]] = (),
        cargos_extra_bs: Iterable[tuple[str, Decimal]] = (),
    ) -> Factura:
        if categoria not in self.tarifas:
            raise ValueError(f"Categoría inválida: {categoria}")
        tarifa = self.tarifas[categoria]
        subtotal_usd, tramos = calcular_consumo(tarifa, consumo_m3)

        cargos: list[tuple[str, Decimal, Decimal]] = []
        for concepto, usd in cargos_extra_usd:
            cargos.append((concepto, _q(usd), _q(usd * tipo_cambio)))
            subtotal_usd += usd
        for concepto, bs in cargos_extra_bs:
            usd_eq = bs / tipo_cambio if tipo_cambio else Decimal("0")
            cargos.append((concepto, _q(usd_eq), _q(bs)))
            subtotal_usd += usd_eq

        monto_usd = _q(subtotal_usd)
        monto_bs = _q(subtotal_usd * tipo_cambio)
        return Factura(
            categoria=categoria,
            consumo_m3=Decimal(consumo_m3),
            monto_usd=monto_usd,
            monto_bs=monto_bs,
            tipo_cambio=tipo_cambio,
            tramos=tramos,
            cargos_extra=cargos,
        )

    # --------------------------------------------------------------------- #
    # Atajos para reglas especiales con descarga industrial.
    # --------------------------------------------------------------------- #
    def facturar_matadero(self, consumo_m3, tipo_cambio):
        usd = descarga_alcantarillado_fija_usd(self.tarifas["CE"], DESCARGA_FIJA_M3["MATADERO"])
        return self.facturar("CE", consumo_m3, tipo_cambio,
                             cargos_extra_usd=[("Descarga industrial Art.15 (600 m³ CE)", usd)])

    def facturar_terminal(self, consumo_m3, tipo_cambio):
        usd = descarga_alcantarillado_fija_usd(self.tarifas["CE"], DESCARGA_FIJA_M3["TERMINAL"])
        return self.facturar("CE", consumo_m3, tipo_cambio,
                             cargos_extra_usd=[("Descarga Art.21 (1200 m³ CE)", usd)])

    def facturar_balneario(self, consumo_m3, tipo_cambio):
        usd = descarga_alcantarillado_fija_usd(self.tarifas["CE"], DESCARGA_FIJA_M3["BALNEARIO"])
        return self.facturar("CE", consumo_m3, tipo_cambio,
                             cargos_extra_usd=[("Descarga Art.22 (480 m³ CE)", usd)])

    def facturar_bano_publico(self, consumo_m3, tipo_cambio):
        usd = descarga_alcantarillado_fija_usd(self.tarifas["CE"], DESCARGA_FIJA_M3["BANO_PUBLICO"])
        return self.facturar("CE", consumo_m3, tipo_cambio,
                             cargos_extra_usd=[("Descarga Art.24 (180 m³ CE)", usd)])

    def facturar_lavanderia(self, consumo_m3, tipo_cambio):
        usd = descarga_alcantarillado_fija_usd(self.tarifas["CE"], DESCARGA_FIJA_M3["LAVANDERIA"])
        return self.facturar("CE", consumo_m3, tipo_cambio,
                             cargos_extra_usd=[("Descarga Art.13 (120 m³ CE)", usd)])

    def facturar_estacion_servicio(self, consumo_m3, tipo_cambio, con_lavadero: bool):
        cat = clasificar_estacion_servicio(con_lavadero)
        extras = []
        if not con_lavadero:
            usd = descarga_alcantarillado_fija_usd(self.tarifas["C"], DESCARGA_FIJA_M3["ESTACION_SERVICIO"])
            extras.append(("Descarga Art.10 (240 m³)", usd))
        return self.facturar(cat, consumo_m3, tipo_cambio, cargos_extra_usd=extras)

    def facturar_lavadero_jeans(self, consumo_m3, tipo_cambio, factor_k: str = "K1"):
        descarga_bs = descarga_art14_bs(factor_k)
        return self.facturar("CE", consumo_m3, tipo_cambio,
                             cargos_extra_bs=[(f"Descarga Art.14 (K={factor_k}, 65 m³)", descarga_bs)])

    def facturar_curtiembre(self, consumo_m3, tipo_cambio, volumen_descarga_m3: int, factor_k: str = "K1"):
        descarga_bs = descarga_art16_bs(volumen_descarga_m3, factor_k)
        # Multa K10
        cargos_bs = [(f"Descarga Art.16 (vol={volumen_descarga_m3} m³, K={factor_k})", descarga_bs)]
        return self.facturar("CE", consumo_m3, tipo_cambio, cargos_extra_bs=cargos_bs)

    def facturar_hospital(self, consumo_m3, tipo_cambio, estatal: bool):
        return self.facturar(clasificar_hospital(estatal), consumo_m3, tipo_cambio)

    def facturar_centro_educativo(self, consumo_m3, tipo_cambio, privado: bool):
        return self.facturar(clasificar_centro_educativo(privado), consumo_m3, tipo_cambio)

    def facturar_restaurante(self, consumo_m3, tipo_cambio, superficie_m2: float):
        return self.facturar(clasificar_restaurante(superficie_m2), consumo_m3, tipo_cambio)


# =============================================================================
# Carga de tarifas desde Cassandra (lazy import para que tests sean puros)
# =============================================================================

def tarifas_desde_filas(rows: Iterable[dict]) -> dict[str, TarifaCategoria]:
    """Convierte filas `SELECT * FROM tarifas` en el mapa `TarifaService` espera."""
    out: dict[str, TarifaCategoria] = {}
    for r in rows:
        out[r["categoria"]] = TarifaCategoria(
            categoria=r["categoria"],
            fijo_m3=Decimal(str(r["fijo_m3"])),
            usd_mes=Decimal(str(r.get("usd_mes", "0"))),
            r_13_25=Decimal(str(r["r_13_25"])),
            r_26_50=Decimal(str(r["r_26_50"])),
            r_51_75=Decimal(str(r["r_51_75"])),
            r_76_100=Decimal(str(r["r_76_100"])),
            r_101_150=Decimal(str(r["r_101_150"])),
            r_mas_151=Decimal(str(r["r_mas_151"])),
        )
    return out
