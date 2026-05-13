"""SEMAPA — Seeder de lecturas históricas (time-series).

Período: 2025-04-01 → hoy. 3 lecturas/día por medidor en bloques:
  - 00-08 (madrugada): residenciales 0..1300 L, resto 0..250 L
  - 08-16 (mañana/mediodía): residenciales 0..380 L, resto 0..250 L
  - 16-24 (tarde/noche): residenciales 0..190 L, resto 0..250 L

Inserta en DOS tablas (denormalización):
  - lecturas_por_medidor   PRIMARY KEY ((medidor_id, anio_mes), fecha_hora)
  - lecturas_por_zona_dia  PRIMARY KEY ((distrito_id, zona_id, fecha), hora, medidor_id)

Acumulado incremental (lectura_litros monótono ascendente).
0.5% con status de error (3..9).

Volumen esperado: 120 000 medidores × 3 / día × ~42 días ≈ 15 M filas.
Tiempo objetivo: < 60 min con concurrency=200.

Variables de entorno:
  LECTURAS_DESDE   (YYYY-MM-DD, default 2025-04-01)
  LECTURAS_HASTA   (YYYY-MM-DD, default hoy)
  LECTURAS_CONCURRENCY (default 200)
  LECTURAS_BATCH   (default 5000 filas por flush concurrente)
  LECTURAS_LIMITE_MEDIDORES (opcional, para pruebas)
"""
from __future__ import annotations

import os
import random
import time
import uuid
from datetime import date, datetime, timedelta

from loguru import logger
from tqdm import tqdm

from cassandra_io import bulk_insert, connect


DESDE = datetime.strptime(os.getenv("LECTURAS_DESDE", "2025-04-01"), "%Y-%m-%d").date()
HASTA = datetime.strptime(os.getenv("LECTURAS_HASTA", date.today().isoformat()), "%Y-%m-%d").date()
CONCURRENCY = int(os.getenv("LECTURAS_CONCURRENCY", "200"))
BATCH = int(os.getenv("LECTURAS_BATCH", "5000"))
LIMITE = int(os.getenv("LECTURAS_LIMITE_MEDIDORES", "0"))  # 0 = sin límite
SEED = int(os.getenv("SEED_RNG", "20250512"))

random.seed(SEED)

BLOQUES = [(2, 8), (10, 14), (18, 22)]  # hora central del bloque
RESIDENCIALES = {"R1", "R2", "R3", "R4"}


def consumo_para(cat: str, bloque_idx: int) -> int:
    if cat in RESIDENCIALES:
        if bloque_idx == 0:
            return random.randint(0, 1300)
        if bloque_idx == 1:
            return random.randint(0, 380)
        return random.randint(0, 190)
    return random.randint(0, 250)


def status_para() -> int:
    r = random.random()
    if r < 0.005:           # 0.5% errores 3..9
        return random.randint(3, 9)
    if r < 0.05:            # 5% manuales
        return 2
    return 1


def fetch_medidores(session) -> list[tuple]:
    """Trae (medidor_id, categoria_tarifa, gateway_id, distrito_id, zona_id)."""
    logger.info("Cargando medidores activos...")
    q = "SELECT medidor_id, categoria_tarifa, gateway_id, distrito_id, zona_id, estado FROM medidores"
    rows = []
    for r in session.execute(q):
        if r.estado == "FUERA_SERVICIO":
            continue
        rows.append((r.medidor_id, r.categoria_tarifa, r.gateway_id, r.distrito_id, r.zona_id))
        if LIMITE and len(rows) >= LIMITE:
            break
    logger.info(f"Medidores listos: {len(rows)}")
    return rows


def fechas() -> list[date]:
    d = DESDE
    out = []
    while d <= HASTA:
        out.append(d)
        d += timedelta(days=1)
    return out


def main():
    t0 = time.time()
    cluster, session = connect()
    try:
        medidores = fetch_medidores(session)
        if not medidores:
            logger.error("No hay medidores. Ejecuta seed.py primero.")
            return

        dias = fechas()
        logger.info(f"Período {DESDE}..{HASTA} ({len(dias)} días) | medidores={len(medidores)}")

        ps_med = session.prepare(
            "INSERT INTO lecturas_por_medidor (medidor_id, anio_mes, fecha_hora, gateway_id, "
            "lectura_litros, consumo_litros, status) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        ps_zona = session.prepare(
            "INSERT INTO lecturas_por_zona_dia (distrito_id, zona_id, fecha, hora, medidor_id, "
            "consumo_litros, categoria_tarifa) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )

        # Lectura acumulada por medidor (en litros, arranca aleatorio entre 100k y 500k)
        acumulado: dict[uuid.UUID, int] = {m[0]: random.randint(100_000, 500_000) for m in medidores}

        rows_med: list[tuple] = []
        rows_zona: list[tuple] = []
        total = 0

        for d in tqdm(dias, desc="dias"):
            anio_mes = d.year * 100 + d.month
            for bidx, hora in enumerate(BLOQUES):
                ts = datetime(d.year, d.month, d.day, hora[0], 0, 0)
                hora_int = hora[0]
                for med_id, cat, gw, dist_id, zona_id in medidores:
                    c = consumo_para(cat, bidx)
                    acumulado[med_id] += c
                    st = status_para()
                    rows_med.append((med_id, anio_mes, ts, gw, acumulado[med_id], c, st))
                    rows_zona.append((dist_id, zona_id, d, hora_int, med_id, c, cat))
                    total += 1
                    if len(rows_med) >= BATCH:
                        bulk_insert(session, ps_med, rows_med, concurrency=CONCURRENCY)
                        bulk_insert(session, ps_zona, rows_zona, concurrency=CONCURRENCY)
                        rows_med.clear()
                        rows_zona.clear()

        if rows_med:
            bulk_insert(session, ps_med, rows_med, concurrency=CONCURRENCY)
            bulk_insert(session, ps_zona, rows_zona, concurrency=CONCURRENCY)

        dt = time.time() - t0
        rate = total / dt if dt else 0
        logger.success(f"Lecturas insertadas: {total:,} en {dt:.1f}s ({rate:,.0f} lect/s)")
    finally:
        cluster.shutdown()


if __name__ == "__main__":
    main()
