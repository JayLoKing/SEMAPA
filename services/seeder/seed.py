"""SEMAPA Seeder — Fase 2.

Pobla catálogos + personas + infraestructuras + medidores + usuarios sistema.

Pasos:
1. Carga Excel (Recursos_Practica_5.xlsx).
2. Escribe CSVs limpios en /data/seeds/.
3. Inserta catálogos en Cassandra.
4. Genera 85 000 personas (80 k naturales + 5 k jurídicas).
5. Distribuye 100 000+ infraestructuras según conteos por zona del Excel.
6. Genera 120 000 medidores (2-4 por infraestructura) con coordenadas con jitter.
7. Inserta 3 usuarios del sistema (alcaldía/gerencia/contabilidad) con bcrypt.

Optimización:
- Prepared statements.
- execute_concurrent_with_args(concurrency=100..200).
- tqdm para progreso.
"""
from __future__ import annotations

import os
import random
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import bcrypt
from cassandra.query import PreparedStatement
from faker import Faker
from loguru import logger
from tqdm import tqdm

from cassandra_io import bulk_insert, connect
from csv_writer import write_csv
from excel_loader import (
    SUB_ALCALDIAS,
    gateways,
    load_distritos_zonas,
    load_errores,
    load_modelos,
    load_tarifas,
    load_tipos_infra,
    load_unidades_educativas,
    load_workbook,
)


EXCEL_PATH = os.getenv("SEEDER_EXCEL", "/recursos/recursos.xlsx")
SEEDS_DIR = Path(os.getenv("SEEDS_DIR", "/data/seeds"))
CONCURRENCY = int(os.getenv("SEED_CONCURRENCY", "120"))
SEED = int(os.getenv("SEED_RNG", "20250512"))

random.seed(SEED)
fake = Faker("es_ES")
Faker.seed(SEED)


CATEGORIAS = ["R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"]


def _bs(text: str) -> bytes:
    return bcrypt.hashpw(text.encode("utf-8"), bcrypt.gensalt(rounds=12))


def jitter(lat: float, lon: float, mag: float = 0.005) -> tuple[float, float]:
    return (lat + random.uniform(-mag, mag), lon + random.uniform(-mag, mag))


def seed_catalogos(session, zonas, distritos, tarifas, modelos, errores, tipos):
    logger.info("Insertando catálogos...")

    # sub_alcaldias
    ps = session.prepare("INSERT INTO sub_alcaldias (sub_alcaldia_id, nombre) VALUES (?, ?)")
    bulk_insert(session, ps, SUB_ALCALDIAS, concurrency=10)

    # distritos
    ps = session.prepare(
        "INSERT INTO distritos (distrito_id, sub_alcaldia_id, nombre, habitantes) VALUES (?, ?, ?, ?)"
    )
    bulk_insert(
        session, ps,
        [(d.distrito_id, d.sub_alcaldia_id, d.nombre, d.habitantes) for d in distritos],
        concurrency=20,
    )

    # zonas
    ps = session.prepare(
        "INSERT INTO zonas (distrito_id, zona_id, nombre, gateway_id) VALUES (?, ?, ?, ?)"
    )
    bulk_insert(
        session, ps,
        [(z.distrito_id, z.zona_id, z.nombre, z.gateway_id) for z in zonas],
        concurrency=40,
    )

    # gateways
    ps = session.prepare(
        "INSERT INTO gateways (gateway_id, nombre, latitud, longitud) VALUES (?, ?, ?, ?)"
    )
    bulk_insert(session, ps, gateways(), concurrency=5)

    # modelos
    ps = session.prepare(
        "INSERT INTO modelos_medidor (modelo_id, marca, modelo, conectividad, aplicacion) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    bulk_insert(
        session, ps,
        [(m.modelo_id, m.marca, m.modelo, m.conectividad, m.aplicacion) for m in modelos],
        concurrency=5,
    )

    # tarifas
    ps = session.prepare(
        "INSERT INTO tarifas (categoria, alias, fijo_m3, usd_mes, r_13_25, r_26_50, "
        "r_51_75, r_76_100, r_101_150, r_mas_151, descripcion) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    bulk_insert(
        session, ps,
        [
            (t.categoria, t.alias, t.fijo_m3, t.usd_mes, t.r_13_25, t.r_26_50,
             t.r_51_75, t.r_76_100, t.r_101_150, t.r_mas_151, t.descripcion)
            for t in tarifas
        ],
        concurrency=5,
    )

    # errores
    ps = session.prepare("INSERT INTO errores_iot (codigo, descripcion) VALUES (?, ?)")
    bulk_insert(session, ps, errores, concurrency=5)

    # tipos infraestructura
    ps = session.prepare("INSERT INTO tipos_infraestructura (tipo_id, descripcion) VALUES (?, ?)")
    bulk_insert(session, ps, [(t.tipo_id, t.descripcion) for t in tipos], concurrency=5)

    logger.success("Catálogos insertados.")


def seed_usuarios(session):
    logger.info("Insertando usuarios del sistema...")
    ps = session.prepare(
        "INSERT INTO usuarios_sistema (username, password_hash, rol, nombre, email, activo, "
        "fecha_creacion, ultimo_acceso) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    now = datetime.utcnow()
    creds = [
        ("alcaldia", _bs("Alcaldia2025!").decode(), "ALCALDIA", "Alcaldía Cochabamba",
         "alcaldia@semapa.bo", True, now, None),
        ("gerencia", _bs("Gerencia2025!").decode(), "GERENCIA", "Gerencia Operativa",
         "gerencia@semapa.bo", True, now, None),
        ("contabilidad", _bs("Contab2025!").decode(), "CONTABILIDAD", "Contabilidad",
         "contabilidad@semapa.bo", True, now, None),
    ]
    bulk_insert(session, ps, creds, concurrency=3)
    logger.success("Usuarios listos: alcaldia / gerencia / contabilidad")


def seed_personas(session, n_naturales: int = 80_000, n_juridicas: int = 5_000) -> list[uuid.UUID]:
    logger.info(f"Generando {n_naturales} personas naturales + {n_juridicas} jurídicas...")
    ps = session.prepare(
        "INSERT INTO personas (persona_id, tipo, documento, nombre, apellidos, razon_social, "
        "email, telefono, fecha_registro) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    ids: list[uuid.UUID] = []
    rows: list[tuple] = []
    now = datetime.utcnow()
    fecha_min = datetime(2018, 1, 1)
    rango_dias = (now - fecha_min).days

    pbar = tqdm(total=n_naturales + n_juridicas, desc="personas")
    for _ in range(n_naturales):
        pid = uuid.uuid4()
        ids.append(pid)
        ci = str(random.randint(1_000_000, 12_999_999))
        rows.append((
            pid, "NATURAL", ci,
            fake.first_name(), fake.last_name() + " " + fake.last_name(),
            None,
            fake.email(), f"7{random.randint(1000000, 9999999)}",
            fecha_min + timedelta(days=random.randint(0, rango_dias)),
        ))
        if len(rows) >= 5000:
            bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
            pbar.update(len(rows))
            rows.clear()

    for _ in range(n_juridicas):
        pid = uuid.uuid4()
        ids.append(pid)
        nit = str(random.randint(100_000_000, 999_999_999))
        rows.append((
            pid, "JURIDICA", nit,
            None, None, fake.company(),
            f"contacto@{fake.domain_name()}", f"4{random.randint(1000000, 9999999)}",
            fecha_min + timedelta(days=random.randint(0, rango_dias)),
        ))
        if len(rows) >= 5000:
            bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
            pbar.update(len(rows))
            rows.clear()

    if rows:
        bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
        pbar.update(len(rows))
    pbar.close()

    logger.success(f"Personas: {len(ids)} insertadas")
    return ids


def seed_infraestructuras_y_medidores(session, zonas, personas_ids, unidades_educativas):
    """Distribuye medidores por zona según los conteos del Excel, agrupados en
    infraestructuras (2-4 medidores por infra) y asignados a personas (1-5 infra
    por persona). Inserta:
      - infraestructuras
      - medidores
    """
    logger.info("Generando infraestructuras + medidores...")
    ps_infra = session.prepare(
        "INSERT INTO infraestructuras (infraestructura_id, persona_id, tipo_infra, "
        "distrito_id, zona_id, direccion, latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    ps_med = session.prepare(
        "INSERT INTO medidores (medidor_id, mac, numero_serie, numero_contrato, "
        "infraestructura_id, modelo_id, categoria_tarifa, gateway_id, distrito_id, zona_id, "
        "latitud, longitud, fecha_instalacion, estado) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    # Cola de personas con cupo aleatorio (1..5 infraestructuras por persona)
    persona_cupo: dict[uuid.UUID, int] = {p: random.randint(1, 5) for p in personas_ids}
    persona_iter = iter(persona_cupo.items())

    def siguiente_persona() -> uuid.UUID:
        nonlocal persona_iter
        while True:
            try:
                pid, cupo = next(persona_iter)
                if cupo > 0:
                    persona_cupo[pid] -= 1
                    return pid
            except StopIteration:
                # se acabaron — reiniciar cupos
                for p in personas_ids:
                    persona_cupo[p] = random.randint(1, 3)
                persona_iter = iter(persona_cupo.items())

    def gen_mac() -> str:
        return ":".join(f"{random.randint(0, 255):02X}" for _ in range(5))

    def gen_serie() -> str:
        return f"SN={random.randint(100, 999)}-{random.randint(10000, 99999)}-{random.randint(1000, 9999)}"

    modelos_disponibles = [1, 2, 3, 4, 5]
    pesos_modelos = [0.30, 0.20, 0.20, 0.15, 0.15]

    contrato_seq = 100_000_000
    fecha_min = date(2020, 1, 1)
    fecha_max = date(2025, 3, 1)
    delta_dias = (fecha_max - fecha_min).days

    infra_rows: list[tuple] = []
    med_rows: list[tuple] = []

    total_infra = 0
    total_med = 0

    # Pre-insertamos infraestructuras correspondientes a unidades educativas (tipo 1)
    educ_pendientes = list(unidades_educativas)

    for zona in tqdm(zonas, desc="zonas"):
        # asignar centroide → posibles ubicaciones
        for cat in CATEGORIAS:
            n_med = zona.counts.get(cat, 0)
            if n_med <= 0:
                continue
            n_infra_zona = max(1, n_med // random.randint(2, 4))
            medidores_por_infra = max(1, n_med // n_infra_zona)

            for i in range(n_infra_zona):
                infra_id = uuid.uuid4()
                persona_id = siguiente_persona()
                tipo_infra = 0  # vivienda normal
                # categoría P → unidades educativas tipo 1, hospitales tipo 2 etc
                if cat == "P" and educ_pendientes:
                    tipo_infra = 1
                    educ_pendientes.pop()
                lat, lon = jitter(zona.centro_lat, zona.centro_lon, 0.008)
                infra_rows.append((
                    infra_id, persona_id, tipo_infra,
                    zona.distrito_id, zona.zona_id,
                    fake.street_address()[:80],
                    lat, lon,
                ))
                total_infra += 1

                # Medidores en esa infra (al menos 1, hasta medidores_por_infra)
                n = min(medidores_por_infra, n_med - i * medidores_por_infra)
                if n <= 0:
                    continue
                for _ in range(n):
                    if total_med >= 120_000:
                        break
                    med_id = uuid.uuid4()
                    modelo_id = random.choices(modelos_disponibles, pesos_modelos)[0]
                    estado_r = random.random()
                    estado = "ACTIVO" if estado_r < 0.95 else ("INACTIVO" if estado_r < 0.98 else "FUERA_SERVICIO")
                    mlat, mlon = jitter(lat, lon, 0.0008)
                    fecha_inst = fecha_min + timedelta(days=random.randint(0, delta_dias))
                    contrato_seq += 1
                    med_rows.append((
                        med_id, gen_mac(), gen_serie(), contrato_seq,
                        infra_id, modelo_id, cat, zona.gateway_id,
                        zona.distrito_id, zona.zona_id, mlat, mlon,
                        fecha_inst, estado,
                    ))
                    total_med += 1

                if len(infra_rows) >= 5000:
                    bulk_insert(session, ps_infra, infra_rows, concurrency=CONCURRENCY)
                    infra_rows.clear()
                if len(med_rows) >= 5000:
                    bulk_insert(session, ps_med, med_rows, concurrency=CONCURRENCY)
                    med_rows.clear()
                if total_med >= 120_000:
                    break
            if total_med >= 120_000:
                break

    if infra_rows:
        bulk_insert(session, ps_infra, infra_rows, concurrency=CONCURRENCY)
    if med_rows:
        bulk_insert(session, ps_med, med_rows, concurrency=CONCURRENCY)

    logger.success(f"Infraestructuras: {total_infra} | Medidores: {total_med}")


def export_csvs(wb, distritos, zonas, tarifas, modelos, errores, tipos):
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(SEEDS_DIR / "sub_alcaldias.csv", ["sub_alcaldia_id", "nombre"], SUB_ALCALDIAS)
    write_csv(
        SEEDS_DIR / "distritos.csv",
        ["distrito_id", "sub_alcaldia_id", "nombre", "habitantes"],
        [(d.distrito_id, d.sub_alcaldia_id, d.nombre, d.habitantes) for d in distritos],
    )
    write_csv(
        SEEDS_DIR / "zonas.csv",
        ["distrito_id", "zona_id", "nombre", "gateway_id", "habitantes", "total_medidores"],
        [(z.distrito_id, z.zona_id, z.nombre, z.gateway_id, z.habitantes, z.total_medidores) for z in zonas],
    )
    write_csv(SEEDS_DIR / "gateways.csv", ["gateway_id", "nombre", "latitud", "longitud"], gateways())
    write_csv(
        SEEDS_DIR / "modelos.csv",
        ["modelo_id", "marca", "modelo", "conectividad", "aplicacion"],
        [(m.modelo_id, m.marca, m.modelo, m.conectividad, m.aplicacion) for m in modelos],
    )
    write_csv(
        SEEDS_DIR / "tarifas.csv",
        ["categoria", "alias", "fijo_m3", "usd_mes", "r_13_25", "r_26_50", "r_51_75",
         "r_76_100", "r_101_150", "r_mas_151", "descripcion"],
        [(t.categoria, t.alias, str(t.fijo_m3), str(t.usd_mes), str(t.r_13_25),
          str(t.r_26_50), str(t.r_51_75), str(t.r_76_100), str(t.r_101_150),
          str(t.r_mas_151), t.descripcion) for t in tarifas],
    )
    write_csv(SEEDS_DIR / "errores.csv", ["codigo", "descripcion"], errores)
    write_csv(
        SEEDS_DIR / "tipos_infra.csv", ["tipo_id", "descripcion"],
        [(t.tipo_id, t.descripcion) for t in tipos],
    )


def main():
    t0 = time.time()
    logger.info("=" * 60)
    logger.info("SEMAPA Seeder — Fase 2")
    logger.info("=" * 60)

    wb = load_workbook(EXCEL_PATH)
    distritos, zonas = load_distritos_zonas(wb)
    tarifas = load_tarifas(wb)
    modelos = load_modelos(wb)
    errores = load_errores(wb)
    tipos = load_tipos_infra(wb)
    unidades = load_unidades_educativas(wb)

    export_csvs(wb, distritos, zonas, tarifas, modelos, errores, tipos)

    cluster, session = connect()
    try:
        seed_catalogos(session, zonas, distritos, tarifas, modelos, errores, tipos)
        seed_usuarios(session)
        personas_ids = seed_personas(session)
        seed_infraestructuras_y_medidores(session, zonas, personas_ids, unidades)
    finally:
        cluster.shutdown()

    logger.success(f"Seed completado en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
