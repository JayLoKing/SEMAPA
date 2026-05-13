"""Tests del TarifaService — Reglamento SEMAPA (Arts. 4–24)."""
from decimal import ROUND_HALF_UP, Decimal

import pytest


def _q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

from app.services.tarifa_service import (
    TarifaCategoria,
    TarifaService,
    calcular_consumo,
    clasificar_centro_educativo,
    clasificar_edificio,
    clasificar_estacion_servicio,
    clasificar_hospedaje,
    clasificar_hospital,
    clasificar_restaurante,
    clasificar_supermercado,
    descarga_art14_bs,
    descarga_art16_bs,
)


def _tarifas_excel() -> dict[str, TarifaCategoria]:
    """Tabla del Excel `Tarifario` (Decimal exacto, en USD)."""
    raw = {
        "R1": ("1.395", "1.10", "1.26", "1.87", "2.39", "2.84", "3.34"),
        "R2": ("2.780833333", "1.78", "1.98", "2.96", "3.59", "4.16", "4.75"),
        "R3": ("5.214166667", "2.17", "3.38", "3.76", "4.36", "4.96", "5.54"),
        "R4": ("8.685", "2.58", "2.80", "4.39", "4.99", "5.59", "6.20"),
        "C":  ("10.43", "5.35", "5.73", "6.14", "6.53", "6.92", "7.34"),
        "CE": ("12.165", "8.72", "8.72", "9.12", "9.50", "9.90", "10.29"),
        "I":  ("9.386666667", "4.95", "5.66", "5.94", "6.33", "6.73", "7.11"),
        "P":  ("4.58", "2.17", "2.39", "2.96", "3.35", "3.76", "4.16"),
        "S":  ("0.67", "0.50", "0.60", "0.70", "0.80", "0.90", "1.00"),
    }
    out: dict[str, TarifaCategoria] = {}
    for c, vals in raw.items():
        out[c] = TarifaCategoria(
            categoria=c,
            fijo_m3=Decimal(vals[0]),
            usd_mes=Decimal(vals[0]),
            r_13_25=Decimal(vals[1]),
            r_26_50=Decimal(vals[2]),
            r_51_75=Decimal(vals[3]),
            r_76_100=Decimal(vals[4]),
            r_101_150=Decimal(vals[5]),
            r_mas_151=Decimal(vals[6]),
        )
    return out


@pytest.fixture
def svc() -> TarifaService:
    return TarifaService(_tarifas_excel())


# ============================================================================
# Cálculo por tramos — 9 categorías
# ============================================================================

@pytest.mark.parametrize("categoria", ["R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"])
def test_consumo_minimo_solo_cargo_fijo(svc: TarifaService, categoria: str):
    """Consumo ≤ 12 m³ → solo cargo fijo."""
    f = svc.facturar(categoria, Decimal("5"), Decimal("6.96"))
    assert f.monto_usd == _tarifas_excel()[categoria].fijo_m3.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert len(f.tramos) == 1
    assert f.tramos[0].m3_facturados == 12


def test_tramos_R3_35m3(svc: TarifaService):
    """R3, 35 m³ → fijo + 13 m³ @ 2.17 + 10 m³ @ 3.38."""
    f = svc.facturar("R3", Decimal("35"), Decimal("6.96"))
    fijo = Decimal("5.214166667")
    tramo_2 = Decimal("13") * Decimal("2.17")
    tramo_3 = Decimal("10") * Decimal("3.38")
    esperado = (fijo + tramo_2 + tramo_3).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert f.monto_usd == esperado
    assert f.tramos[1].desde_m3 == 13 and f.tramos[1].hasta_m3 == 25
    assert f.tramos[2].desde_m3 == 26 and f.tramos[2].hasta_m3 == 35


def test_tramos_R4_175m3(svc: TarifaService):
    """R4, 175 m³ → fijo + 13×2.58 + 25×2.80 + 25×4.39 + 25×4.99 + 50×5.59 + 25×6.20."""
    f = svc.facturar("R4", Decimal("175"), Decimal("6.96"))
    base = (
        Decimal("8.685")
        + Decimal("13") * Decimal("2.58")
        + Decimal("25") * Decimal("2.80")
        + Decimal("25") * Decimal("4.39")
        + Decimal("25") * Decimal("4.99")
        + Decimal("50") * Decimal("5.59")
        + Decimal("25") * Decimal("6.20")
    )
    assert f.monto_usd == base.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def test_conversion_bs(svc: TarifaService):
    f = svc.facturar("R1", Decimal("20"), Decimal("6.96"))
    subtotal_unrounded = sum((t.subtotal_usd for t in f.tramos), Decimal("0"))
    assert f.monto_bs == _q(subtotal_unrounded * Decimal("6.96"))


# ============================================================================
# Clasificadores Art. 6, 7, 9, 10, 17, 18, 20
# ============================================================================

def test_art6_edificios():
    assert clasificar_edificio("DEPARTAMENTOS") == "R3"
    assert clasificar_edificio("MIXTO") == "R4"
    assert clasificar_edificio("CONDOMINIO") == "R4"
    assert clasificar_edificio("GALERIA") == "C"


def test_art7_supermercados():
    assert clasificar_supermercado("MINI") == "R4"
    assert clasificar_supermercado("SUPER") == "C"
    assert clasificar_supermercado("HIPER") == "CE"


def test_art9_hospedajes():
    assert clasificar_hospedaje(2, "HOTEL") == "C"
    assert clasificar_hospedaje(3, "HOTEL") == "C"
    assert clasificar_hospedaje(4, "HOTEL") == "CE"
    assert clasificar_hospedaje(5, "HOTEL") == "CE"
    assert clasificar_hospedaje(3, "MOTEL") == "CE"
    assert clasificar_hospedaje(2, "APART") == "C"


def test_art10_estaciones_servicio():
    assert clasificar_estacion_servicio(con_lavadero=False) == "C"
    assert clasificar_estacion_servicio(con_lavadero=True) == "CE"


def test_art17_restaurantes():
    assert clasificar_restaurante(30) == "R4"
    assert clasificar_restaurante(40) == "R4"
    assert clasificar_restaurante(41) == "C"
    assert clasificar_restaurante(100) == "C"
    assert clasificar_restaurante(101) == "CE"
    assert clasificar_restaurante(500) == "CE"


def test_art18_hospitales():
    assert clasificar_hospital(estatal=True) == "P"
    assert clasificar_hospital(estatal=False) == "CE"


def test_art20_centros_educativos():
    assert clasificar_centro_educativo(privado=True) == "CE"
    assert clasificar_centro_educativo(privado=False) == "P"


# ============================================================================
# Descargas industriales Arts. 13–16, 21, 22, 24
# ============================================================================

def test_art14_descarga_jeans_K1():
    assert descarga_art14_bs("K1") == Decimal("204.00")


def test_art14_descarga_jeans_K3():
    assert descarga_art14_bs("K3") == Decimal("244.80")


def test_art16_curtiembre_rangos():
    assert descarga_art16_bs(50, "K1") == Decimal("218.50")
    assert descarga_art16_bs(100, "K1") == Decimal("470.00")
    assert descarga_art16_bs(200, "K1") == Decimal("1004.00")


def test_art16_curtiembre_factor_K():
    # 100 m³ × K2 = 470 × 1.10 = 517
    assert descarga_art16_bs(100, "K2") == Decimal("517.00")


def test_art16_curtiembre_volumen_mayor_300():
    # 401 m³ → 300 m³ base (1004) + 200 m³ extra → 2 bloques de 100 → +30% × 2 = +60%
    # Implementación: extra_bloques = ceil((401-300)/100) = 2 → 1004 × (1 + 0.30*2) = 1004 × 1.60 = 1606.40
    result = descarga_art16_bs(401, "K1")
    assert result == Decimal("1606.40")


def test_facturar_matadero_incluye_descarga(svc: TarifaService):
    f = svc.facturar_matadero(Decimal("30"), Decimal("6.96"))
    assert f.categoria == "CE"
    assert any("Art.15" in c[0] for c in f.cargos_extra)


def test_facturar_terminal_incluye_descarga(svc: TarifaService):
    f = svc.facturar_terminal(Decimal("50"), Decimal("6.96"))
    assert any("Art.21" in c[0] for c in f.cargos_extra)


def test_facturar_estacion_sin_lavadero(svc: TarifaService):
    f = svc.facturar_estacion_servicio(Decimal("20"), Decimal("6.96"), con_lavadero=False)
    assert f.categoria == "C"
    assert any("Art.10" in c[0] for c in f.cargos_extra)


def test_facturar_estacion_con_lavadero_es_CE(svc: TarifaService):
    f = svc.facturar_estacion_servicio(Decimal("20"), Decimal("6.96"), con_lavadero=True)
    assert f.categoria == "CE"


def test_facturar_lavadero_jeans_aplica_K(svc: TarifaService):
    f = svc.facturar_lavadero_jeans(Decimal("40"), Decimal("6.96"), factor_k="K2")
    # cargo_extra Bs = 204 × 1.10 = 224.40
    assert any(c[2] == Decimal("224.40") for c in f.cargos_extra)


def test_categoria_invalida(svc: TarifaService):
    with pytest.raises(ValueError):
        svc.facturar("X1", 10, Decimal("6.96"))


def test_construir_sin_categoria_completa():
    incompletas = {k: v for k, v in _tarifas_excel().items() if k != "S"}
    with pytest.raises(ValueError):
        TarifaService(incompletas)
