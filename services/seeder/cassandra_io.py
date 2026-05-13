"""Conexión y helpers Cassandra para el seeder.

- Cluster con token-aware + DC-aware routing.
- Prepared statements compilados una vez.
- execute_concurrent_with_args para escrituras masivas (concurrency configurable).
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Iterable

from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT, Session
from cassandra.concurrent import execute_concurrent_with_args
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy
from cassandra.query import PreparedStatement
from loguru import logger


def connect(retries: int = 30, delay: float = 5.0) -> tuple[Cluster, Session]:
    hosts = os.getenv("CASSANDRA_HOSTS", "cassandra-1,cassandra-2").split(",")
    port = int(os.getenv("CASSANDRA_PORT", "9042"))
    keyspace = os.getenv("CASSANDRA_KEYSPACE", "semapa")
    user = os.getenv("CASSANDRA_USER", "")
    pwd = os.getenv("CASSANDRA_PASSWORD", "")

    auth = PlainTextAuthProvider(username=user, password=pwd) if user else None
    profile = ExecutionProfile(
        load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy(local_dc="datacenter1")),
        consistency_level=ConsistencyLevel.LOCAL_QUORUM,
        request_timeout=60.0,
    )

    last: Exception | None = None
    for i in range(retries):
        try:
            cluster = Cluster(
                contact_points=hosts,
                port=port,
                auth_provider=auth,
                execution_profiles={EXEC_PROFILE_DEFAULT: profile},
                protocol_version=5,
            )
            session = cluster.connect(keyspace)
            logger.info(f"Cassandra conectado en {hosts}:{port} keyspace={keyspace}")
            return cluster, session
        except Exception as e:
            last = e
            logger.warning(f"Cassandra no disponible ({i+1}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError(f"No se pudo conectar a Cassandra tras {retries} intentos: {last}")


def bulk_insert(
    session: Session,
    prepared: PreparedStatement,
    rows: Iterable[tuple],
    concurrency: int = 100,
    raise_on_first_error: bool = False,
) -> int:
    """Inserta usando execute_concurrent_with_args. Devuelve filas exitosas."""
    parameters = list(rows)
    if not parameters:
        return 0
    results = execute_concurrent_with_args(
        session,
        prepared,
        parameters,
        concurrency=concurrency,
        raise_on_first_error=raise_on_first_error,
    )
    ok = sum(1 for r in results if r.success)
    fail = len(results) - ok
    if fail:
        logger.warning(f"bulk_insert: {fail} fallos de {len(results)}")
    return ok
