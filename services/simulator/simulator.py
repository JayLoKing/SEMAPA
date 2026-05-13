"""SEMAPA - Simulador LoRaWAN.

Genera archivos `.txt` por medidor en
`/lora-data/{gateway_name}/{YYYY-MM-DD-HH}/{mac}.txt` con formato:

    MACMedidor,Fecha,Antena,Lectura,Status
    AB:CB:12:13:56,2025-05-12 15:30:00,1,001234.67,1

Modos:
  - Servicio HTTP (FastAPI) — endpoint `/simulate/burst?n=600`.
  - Loop horario opcional (`SIM_LOOP=1`): cada hora dispara `BURST_SIZE` lecturas.

Parametrización:
  SIM_INTERVAL_S         (default 3600)
  BURST_SIZE             (default 600)
  ERROR_RATE             (default 0.005)
  DUPLICATE_RATE         (default 0.0007)
  LORA_DIR               (default /lora-data)
"""
from __future__ import annotations

import asyncio
import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster, Session
from fastapi import FastAPI, Query
from loguru import logger

LORA_DIR = Path(os.getenv("LORA_DIR", "/lora-data"))
BURST_SIZE = int(os.getenv("BURST_SIZE", "600"))
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.005"))
DUPLICATE_RATE = float(os.getenv("DUPLICATE_RATE", "0.0007"))
SIM_LOOP = os.getenv("SIM_LOOP", "1") == "1"
SIM_INTERVAL_S = int(os.getenv("SIM_INTERVAL_S", "3600"))

CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra-1,cassandra-2").split(",")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "semapa")
CASSANDRA_USER = os.getenv("CASSANDRA_USER", "")
CASSANDRA_PASSWORD = os.getenv("CASSANDRA_PASSWORD", "")


GATEWAY_NAMES = {
    1: "LoRaWan-Teleferico",
    2: "LoRaWan-ParqueVial",
    3: "LoRaWan-ParqueLincon",
    4: "LoRaWan-Petrolera",
    5: "LoRaWan-SurEste",
}


def _connect() -> tuple[Cluster, Session]:
    auth = None
    if CASSANDRA_USER:
        auth = PlainTextAuthProvider(username=CASSANDRA_USER, password=CASSANDRA_PASSWORD)
    cluster = Cluster(
        contact_points=CASSANDRA_HOSTS,
        port=CASSANDRA_PORT,
        auth_provider=auth,
        protocol_version=5,
    )
    return cluster, cluster.connect(CASSANDRA_KEYSPACE)


def _sample_medidores(session: Session, n: int) -> list[dict]:
    """Trae una muestra aleatoria. Para volumen real se usa LIMIT alto y se sub-muestrea."""
    rows = list(session.execute(
        f"SELECT medidor_id, mac, gateway_id FROM medidores LIMIT {max(n * 4, n)}"
    ))
    if not rows:
        return []
    random.shuffle(rows)
    return rows[:n]


def _status() -> int:
    r = random.random()
    if r < ERROR_RATE:
        return random.randint(3, 9)
    if r < 0.05:
        return 2
    return 1


def _payload_line(mac: str, gw: int, lectura: float, status: int, ts: datetime) -> str:
    return f"{mac},{ts.strftime('%Y-%m-%d %H:%M:%S')},{gw},{lectura:09.2f},{status}\n"


def _write_file(gateway_id: int, mac: str, ts: datetime, payload: str) -> Path:
    name = GATEWAY_NAMES.get(gateway_id, f"LoRaWan-{gateway_id}")
    bucket = LORA_DIR / name / ts.strftime("%Y-%m-%d-%H")
    bucket.mkdir(parents=True, exist_ok=True)
    safe_mac = mac.replace(":", "_")
    # nombre incluye uuid corto para no chocar entre lecturas del mismo medidor en la misma carpeta
    fp = bucket / f"{safe_mac}_{uuid.uuid4().hex[:6]}.txt"
    fp.write_text(payload, encoding="utf-8")
    return fp


def generate_burst(session: Session, n: int) -> dict:
    medidores = _sample_medidores(session, n)
    if not medidores:
        logger.warning("Sin medidores. Ejecutaste seed.py?")
        return {"generated": 0, "files": 0, "duplicated": 0}

    ts = datetime.now(timezone.utc).replace(tzinfo=None)
    n_files = 0
    n_dups = 0
    for m in medidores:
        mac = m["mac"] if isinstance(m, dict) else m.mac
        gw = m["gateway_id"] if isinstance(m, dict) else m.gateway_id
        lectura = round(random.uniform(100_000, 999_999) / 1000, 2)
        status = _status()
        payload = (
            "MACMedidor,Fecha,Antena,Lectura,Status\n"
            + _payload_line(mac, gw, lectura, status, ts)
        )
        _write_file(gw, mac, ts, payload)
        n_files += 1
        if random.random() < DUPLICATE_RATE:
            # duplicado con timestamp ligeramente distinto
            dup_ts = ts.replace(microsecond=random.randint(1, 999) * 1000)
            _write_file(gw, mac, dup_ts, payload)
            n_files += 1
            n_dups += 1
    logger.info(f"Burst: medidores={len(medidores)} archivos={n_files} duplicados={n_dups}")
    return {"generated": len(medidores), "files": n_files, "duplicated": n_dups}


# ----------------------- FastAPI service -----------------------
app = FastAPI(title="SEMAPA Simulator")
_cluster: Cluster | None = None
_session: Session | None = None


@app.on_event("startup")
async def startup():
    global _cluster, _session
    LORA_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(30):
        try:
            _cluster, _session = _connect()
            logger.info("Cassandra conectado")
            break
        except Exception as e:
            logger.warning(f"Reintento Cassandra ({i+1}/30): {e}")
            await asyncio.sleep(5)
    if SIM_LOOP:
        asyncio.create_task(_loop())


@app.on_event("shutdown")
async def shutdown():
    if _cluster:
        _cluster.shutdown()


async def _loop():
    while True:
        try:
            generate_burst(_session, BURST_SIZE)
        except Exception as e:
            logger.error(f"Loop error: {e}")
        await asyncio.sleep(SIM_INTERVAL_S)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "simulator"}


@app.post("/simulate/burst")
async def burst(n: int = Query(BURST_SIZE, ge=1, le=10000)):
    if _session is None:
        return {"error": "Cassandra no conectado"}
    return generate_burst(_session, n)


if __name__ == "__main__":
    # CLI rápida
    cluster, session = _connect()
    try:
        for _ in range(5):
            generate_burst(session, 120)
            time.sleep(1)
    finally:
        cluster.shutdown()
