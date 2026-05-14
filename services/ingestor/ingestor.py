"""SEMAPA — Ingestor (watcher /lora-data → Cassandra).

Pipeline:
  1. Observa `/lora-data/**/*.txt` con watchdog (PollingObserver para volúmenes
     Docker en Windows host).
  2. Parsea cada archivo: cabecera + filas `mac, fecha, antena, lectura, status`.
  3. Deduplica con Redis (key=`dedup:{mac}:{ts}`, TTL 24h).
  4. Inserta en `lecturas_por_medidor` + `lecturas_por_zona_dia` + `lecturas_raw`.
  5. Mantiene métricas in-process expuestas vía HTTP (puerto 8003).

Optimizaciones:
  - Prepared statements compilados una vez.
  - Cache local de `mac → (medidor_id, dist, zona, categoria)` (LRU).
  - Inserciones por lote con `execute_concurrent_with_args`.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Iterable

import redis
from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster, Session
from cassandra.concurrent import execute_concurrent_with_args
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy
from cassandra.query import dict_factory
from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver


# ---------------------- config ----------------------
WATCH_DIR = Path(os.getenv("INGESTOR_WATCH_DIR", "/lora-data"))
METRICS_PORT = int(os.getenv("INGESTOR_METRICS_PORT", "8003"))
DEDUP_TTL = int(os.getenv("DEDUP_TTL_SECONDS", "86400"))
CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra-1,cassandra-2").split(",")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "semapa")
CASSANDRA_USER = os.getenv("CASSANDRA_USER", "")
CASSANDRA_PASSWORD = os.getenv("CASSANDRA_PASSWORD", "")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


# ---------------------- metrics ----------------------
ANOMALY_THRESHOLD = int(os.getenv("ANOMALY_THRESHOLD_LITROS", "50000"))  # 50m³ salto = anomalía

METRICS = {
    "files_processed": 0,
    "rows_inserted": 0,
    "duplicates_skipped": 0,
    "errors": 0,
    "parse_errors": 0,
    "anomalies_detected": 0,
    "started_at": datetime.utcnow().isoformat() + "Z",
}


# ---------------------- cassandra ----------------------
def connect_cassandra() -> tuple[Cluster, Session]:
    auth = PlainTextAuthProvider(CASSANDRA_USER, CASSANDRA_PASSWORD) if CASSANDRA_USER else None
    cluster = Cluster(
        contact_points=CASSANDRA_HOSTS,
        port=CASSANDRA_PORT,
        auth_provider=auth,
        protocol_version=5,
    )
    session = cluster.connect(CASSANDRA_KEYSPACE)
    session.row_factory = dict_factory
    session.default_consistency_level = ConsistencyLevel.LOCAL_QUORUM
    return cluster, session


class State:
    cluster: Cluster | None = None
    session: Session | None = None
    redis: redis.Redis | None = None
    ps_lecturas: any = None
    ps_lecturas_zona: any = None
    ps_lecturas_raw: any = None


def init_state() -> None:
    for i in range(30):
        try:
            State.cluster, State.session = connect_cassandra()
            break
        except Exception as e:
            logger.warning(f"Cassandra retry {i+1}/30: {e}")
            time.sleep(5)
    State.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    State.ps_lecturas = State.session.prepare(
        "INSERT INTO lecturas_por_medidor (medidor_id, anio_mes, fecha_hora, gateway_id, "
        "lectura_litros, consumo_litros, status) VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    State.ps_lecturas_zona = State.session.prepare(
        "INSERT INTO lecturas_por_zona_dia (distrito_id, zona_id, fecha, hora, medidor_id, "
        "consumo_litros, categoria_tarifa) VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    State.ps_lecturas_raw = State.session.prepare(
        "INSERT INTO lecturas_raw (gateway_id, fecha, ts, mac, payload, procesado, error_motivo) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    logger.info("Ingestor inicializado (Cassandra + Redis + Prepared)")


# ---------------------- lookup ----------------------
@lru_cache(maxsize=200_000)
def lookup_medidor(mac: str) -> tuple | None:
    rows = list(State.session.execute(
        "SELECT medidor_id, distrito_id, zona_id, categoria_tarifa, gateway_id FROM medidores WHERE mac = %s",
        (mac,),
    ))
    if not rows:
        return None
    r = rows[0]
    return (r["medidor_id"], r["distrito_id"], r["zona_id"], r["categoria_tarifa"], r["gateway_id"])


# ---------------------- parsing ----------------------
def parse_file(path: Path) -> Iterable[tuple]:
    """Yields (mac, ts, antena, lectura_float, status, raw_line)."""
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip() or line.startswith("MACMedidor"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        mac, fecha, antena, lectura, status = parts[:5]
        try:
            ts = datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S")
            yield (mac.upper(), ts, int(antena), float(lectura), int(status), line)
        except ValueError:
            METRICS["parse_errors"] += 1
            continue


def process_file(path: Path) -> None:
    METRICS["files_processed"] += 1
    rows_med: list[tuple] = []
    rows_zona: list[tuple] = []
    rows_raw: list[tuple] = []

    for mac, ts, antena, lectura, status, raw_line in parse_file(path):
        dedup_key = f"dedup:{mac}:{ts.isoformat()}"
        try:
            if not State.redis.set(dedup_key, "1", ex=DEDUP_TTL, nx=True):
                METRICS["duplicates_skipped"] += 1
                continue
        except Exception as e:
            logger.warning(f"Redis dedup falló: {e}")

        meta = lookup_medidor(mac)
        if not meta:
            rows_raw.append((antena, ts.date(), ts, mac, raw_line, False, "mac_no_encontrado"))
            continue
        medidor_id, dist_id, zona_id, cat, gw = meta
        litros = int(lectura * 1000)
        anio_mes = ts.year * 100 + ts.month

        # ---- Consumo diferencial + detección de anomalías ----
        last_key = f"last_lectura:{mac}"
        consumo = 0
        flag_status = status  # 1=OK, 2=Manual, 3..9=errores
        try:
            last_val = State.redis.get(last_key)
            if last_val is not None:
                consumo = litros - int(last_val)
                if consumo < 0:
                    # Reseteo de medidor o lectura negativa (reemplaza contador)
                    consumo = litros
                    flag_status = 8  # RESET
                    logger.warning(f"RESET medidor {mac}: delta={consumo}")
                elif consumo > ANOMALY_THRESHOLD:
                    flag_status = 9  # ANOMALIA: salto imposible
                    METRICS["anomalies_detected"] += 1
                    logger.warning(f"ANOMALIA {mac}: consumo={consumo}L threshold={ANOMALY_THRESHOLD}L")
            State.redis.set(last_key, litros)
        except Exception as e:
            logger.warning(f"Redis anomaly check falló: {e}")

        rows_med.append((medidor_id, anio_mes, ts, gw or antena, litros, consumo, flag_status))
        rows_zona.append((dist_id, zona_id, ts.date(), ts.hour, medidor_id, consumo, cat))
        rows_raw.append((gw or antena, ts.date(), ts, mac, raw_line, True, None))

    if rows_med:
        try:
            execute_concurrent_with_args(State.session, State.ps_lecturas, rows_med, concurrency=50)
            execute_concurrent_with_args(State.session, State.ps_lecturas_zona, rows_zona, concurrency=50)
            METRICS["rows_inserted"] += len(rows_med)
        except Exception as e:
            METRICS["errors"] += 1
            logger.error(f"Error inserción: {e}")
    if rows_raw:
        try:
            execute_concurrent_with_args(State.session, State.ps_lecturas_raw, rows_raw, concurrency=50)
        except Exception as e:
            logger.warning(f"lecturas_raw insert error: {e}")


# ---------------------- watcher ----------------------
class TxtHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".txt"):
            return
        try:
            # Pequeño delay para asegurar escritura completa.
            time.sleep(0.05)
            process_file(Path(event.src_path))
        except Exception as e:
            METRICS["errors"] += 1
            logger.error(f"process_file({event.src_path}) falló: {e}")


# ---------------------- metrics http ----------------------
class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        import json
        body = json.dumps(METRICS).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args, **kwargs):
        pass


def serve_metrics():
    srv = HTTPServer(("0.0.0.0", METRICS_PORT), MetricsHandler)
    srv.serve_forever()


# ---------------------- main ----------------------
def main():
    logger.info(f"Ingestor watching {WATCH_DIR}")
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    init_state()
    threading.Thread(target=serve_metrics, daemon=True).start()

    observer = PollingObserver(timeout=1.0)
    observer.schedule(TxtHandler(), str(WATCH_DIR), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(60)
            logger.info(f"metrics: {METRICS}")
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    if State.cluster:
        State.cluster.shutdown()


if __name__ == "__main__":
    main()
