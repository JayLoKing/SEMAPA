# Reglamento Tarifario SEMAPA — Resumen ejecutivo

Fuente: `REGLAMENTO DE POLITICA TARIFARIA.pdf` (Reglamento Interno, aprobado
07-sep-2004). Implementación: `services/api/app/services/tarifa_service.py`.

## Capítulo I — Categorías (Art. 4)

| Código | Descripción                                                                |
|--------|----------------------------------------------------------------------------|
| R1     | Doméstico — lotes con acometida hasta rasante, casa deshabitada o litigio |
| R2     | Doméstico — casas precarias                                                |
| R3     | Doméstico — construcción económica, departamentos, predios en obra        |
| R4     | Doméstico — casa confortable con servicios, condominios                   |
| C      | Comercial — predio para negocio                                            |
| CE     | Comercial Especial — agua como insumo o proceso                           |
| I      | Industrial — talleres, fábricas, panaderías                               |
| P      | Preferencial — predios estatales con fines sociales                        |
| S      | Social                                                                     |

> Adicionalmente, la categoría **M (Mixto)** del Reglamento se resuelve por
> apreciación a P/M/G y se mapea a R3/R4/C/CE; nuestra implementación expone
> `clasificar_edificio`, `clasificar_supermercado`, etc.

## Cargo fijo + tramos progresivos

- **Cargo fijo**: primeros **12 m³/mes**, USD según categoría (tabla `Tarifario`).
- **Tramos progresivos** por m³ (USD/m³ por categoría):

| Tramo     | m³ del tramo |
|-----------|--------------|
| 13–25     | 13           |
| 26–50     | 25           |
| 51–75     | 25           |
| 76–100    | 25           |
| 101–150   | 50           |
| ≥ 151     | resto        |

Conversión a Bs con el tipo de cambio del periodo (`TarifaService.facturar(...).monto_bs`).

## Reglas especiales por capítulo

| Art. | Tipo de usuario              | Categoría base | Descarga/Cargo fijo                                        |
|------|------------------------------|----------------|------------------------------------------------------------|
| 6    | Edificios solo deptos.       | R3             | Bs 17/depto sin medidor                                    |
| 6    | Edificios mixtos             | R4             | Bs 17/depto + Bs 31.5/oficina                              |
| 6    | Condominios                  | R4             | Bs 31.5/depto                                              |
| 6    | Centros comerciales/galerías | C              | R4 (Bs 31.5)                                               |
| 7    | Mini-supermercado            | R4             | —                                                          |
| 7    | Supermercado                 | C              | —                                                          |
| 7    | Hipermercado                 | CE             | **+ 400 m³/CE fijos**                                      |
| 8    | Licorerías                   | R4 / C         | proporcional                                               |
| 9    | Hoteles 1–3 ★                | C              | 3 m³/habitación/mes sin medidor                            |
| 9    | Hoteles 4–5 ★, moteles       | CE             | idem                                                       |
| 10   | Estación de servicio         | C              | **240 m³** fijos                                           |
| 10   | Est. servicio + lavadero     | CE             | —                                                          |
| 11   | Lab. fotográfico             | C              | **Bs 101.50** descarga industrial (≡ 45 m³ C)              |
| 12   | Estudio fotográfico          | C              | sin descarga industrial                                    |
| 13   | Lavanderías seco/vapor       | CE             | **120 m³/CE** fijos                                        |
| 14   | Lavadero de jeans            | CE             | **Bs 204 × K** (K1=1, K2=1.10, …, K5=1.45)                 |
| 15   | Mataderos                    | CE             | **600 m³/CE** fijos                                        |
| 16   | Curtiembres / metal-mecánicas| CE             | rangos por volumen × K (ver abajo)                         |
| 17   | Restaurante ≤ 40 m²          | R4             | 45 m³ fijos                                                |
| 17   | Restaurante 41–100 m²        | C              | 90 m³ fijos                                                |
| 17   | Restaurante ≥ 101 m²         | CE             | 120 m³ fijos                                               |
| 18   | Hospitales estatales         | P              | 3 m³/cama/mes                                              |
| 18   | Hospitales privados          | CE             | idem                                                       |
| 19   | Laboratorios clínicos        | C              | —                                                          |
| 20   | Centros educativos privados  | CE             | 50 L/día/alumno sin medidor                                |
| 21   | Terminales de pasajeros      | CE             | **1200 m³/CE** fijos                                       |
| 22   | Balnearios, piscinas, saunas | CE             | **480 m³/CE** fijos                                        |
| 23   | Fábricas de bebidas/hielo    | CE             | —                                                          |
| 24   | Baños públicos               | CE             | **180 m³/CE** fijos                                        |

### Art. 16 — Curtiembres / metal-mecánicas

Volumen de descarga industrial (Bs, base):

| Volumen        | Bs       |
|----------------|----------|
| 0 – 70 m³      | 218.50   |
| 71 – 150 m³    | 470.00   |
| 151 – 300 m³   | 1004.00  |
| > 300 m³       | 1004 × (1 + 0.30 × ⌈(v-300)/100⌉) |

Multiplicado por factor K (coeficiente de contaminación):

| K   | Rango contaminación | Multiplicador |
|-----|---------------------|---------------|
| K1  | 0.6 – 4.5           | 1.00          |
| K2  | 4.5 – 9.0           | 1.10          |
| K3  | 9.1 – 15.0          | 1.20          |
| K4  | 15.1 – 25.0         | 1.33          |
| K5  | 25.1 – 40.0         | 1.45          |

Si K > K10 → multa **Bs 5 000** (Art. 16).

### Art. 14 — Lavadero de jeans

Descarga fija **Bs 204** (≡ 65 m³ CE) multiplicada por factor K idéntico al
Art. 16.

## Capítulo XVII — Sanciones / Cortes (Arts. 25–26)

- 2 facturas vencidas → corte normal
- 4 facturas → corte físico
- 10 facturas → retiro de servicios. Costos de rehabilitación: **Bs 578**
  (alcantarillado) + **Bs 73.50** (agua).

## Capítulo XVIII — Descuentos (Art. 27)

- Pago al contado de deuda contraída → descuento **40 %**.
- Plan de pagos → según Reglamento Interno de Regularizaciones (Res. 06/2004).

## Implementación

```python
from app.services.tarifa_service import TarifaService, tarifas_desde_filas

# 1) carga tarifas desde Cassandra
rows = session.execute("SELECT * FROM tarifas").all()
svc = TarifaService(tarifas_desde_filas([dict(r._asdict()) for r in rows]))

# 2) facturación estándar
factura = svc.facturar("R3", consumo_m3=35, tipo_cambio=Decimal("6.96"))

# 3) reglas especiales
matadero = svc.facturar_matadero(50, Decimal("6.96"))
estacion = svc.facturar_estacion_servicio(20, Decimal("6.96"), con_lavadero=False)
jeans    = svc.facturar_lavadero_jeans(40, Decimal("6.96"), factor_k="K2")
curt     = svc.facturar_curtiembre(80, Decimal("6.96"),
                                   volumen_descarga_m3=200, factor_k="K3")
```

Tests: `services/api/tests/test_tarifa.py` (31 casos cubriendo las 9 categorías
y los Arts. 6, 7, 9, 10, 14, 15, 16, 17, 18, 20, 21, 22).
