"""Cassandra client singleton + prepared statements.

Conexión inicial al startup, cierre limpio al shutdown.
Prepared statements compilados una sola vez en `prepare_statements()`.
"""
from __future__ import annotations

import asyncio
from typing import Any, Iterable

from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import (EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile,
                               Session)
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy
from cassandra.query import PreparedStatement, dict_factory
from loguru import logger

from app.core.config import settings


class CassandraClient:
    def __init__(self) -> None:
        self.cluster: Cluster | None = None
        self.session: Session | None = None
        self.prepared: dict[str, PreparedStatement] = {}

    def connect(self) -> None:
        if self.cluster is not None:
            return
        hosts = [h.strip() for h in settings.CASSANDRA_HOSTS.split(",") if h.strip()]
        auth = None
        if settings.CASSANDRA_USER:
            auth = PlainTextAuthProvider(
                username=settings.CASSANDRA_USER,
                password=settings.CASSANDRA_PASSWORD,
            )
        profile = ExecutionProfile(
            load_balancing_policy=TokenAwarePolicy(
                DCAwareRoundRobinPolicy(local_dc=settings.CASSANDRA_DC)
            ),
            consistency_level=ConsistencyLevel.LOCAL_QUORUM,
            request_timeout=30.0,
            row_factory=dict_factory,
        )
        # Profile específico para queries analíticas pesadas → ONE
        profile_one = ExecutionProfile(
            load_balancing_policy=TokenAwarePolicy(
                DCAwareRoundRobinPolicy(local_dc=settings.CASSANDRA_DC)
            ),
            consistency_level=ConsistencyLevel.ONE,
            request_timeout=60.0,
            row_factory=dict_factory,
        )
        self.cluster = Cluster(
            contact_points=hosts,
            port=settings.CASSANDRA_PORT,
            auth_provider=auth,
            execution_profiles={
                EXEC_PROFILE_DEFAULT: profile,
                "analytics": profile_one,
            },
            protocol_version=5,
        )
        self.session = self.cluster.connect(settings.CASSANDRA_KEYSPACE)
        logger.info(f"Cassandra conectado a {hosts}:{settings.CASSANDRA_PORT}")

    def prepare_statements(self) -> None:
        assert self.session is not None
        ps = self.session.prepare
        self.prepared.update({
            # auth
            "auth_get_user": ps("SELECT * FROM usuarios_sistema WHERE username = ?"),
            "auth_touch_user": ps("UPDATE usuarios_sistema SET ultimo_acceso = ? WHERE username = ?"),
            # buscar
            "find_medidor_by_mac": ps("SELECT * FROM medidores WHERE mac = ?"),
            "find_medidor_by_contrato": ps("SELECT * FROM medidores WHERE numero_contrato = ?"),
            "find_medidor_by_serie": ps("SELECT * FROM medidores WHERE numero_serie = ?"),
            "find_persona_by_doc": ps("SELECT * FROM personas WHERE documento = ?"),
            # tarifas
            "list_tarifas": ps("SELECT * FROM tarifas"),
            # lecturas
            "lecturas_de_medidor": ps(
                "SELECT * FROM lecturas_por_medidor WHERE medidor_id = ? AND anio_mes = ? LIMIT ?"
            ),
            "lecturas_zona_fecha": ps(
                "SELECT * FROM lecturas_por_zona_dia WHERE distrito_id = ? AND zona_id = ? AND fecha = ?"
            ),
            # facturas
            "factura_get": ps("SELECT * FROM facturas WHERE numero_contrato = ? AND periodo = ?"),
            "factura_put": ps(
                "INSERT INTO facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, "
                "consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, "
                "fecha_emision, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            "factura_periodo_put": ps(
                "INSERT INTO facturas_por_periodo (periodo, distrito_id, numero_contrato, monto_usd, "
                "consumo_m3, categoria_tarifa) VALUES (?, ?, ?, ?, ?, ?)"
            ),
            # lecturas manuales (app móvil)
            "lectura_manual_put": ps(
                "INSERT INTO lecturas_manuales (medidor_id, fecha_hora, usuario, lectura_litros, "
                "lat, lon, foto_url) VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
        })
        logger.info(f"Prepared statements compilados: {len(self.prepared)}")

    def execute(self, key: str, params: tuple | list = (), profile: str = EXEC_PROFILE_DEFAULT):
        assert self.session is not None
        return self.session.execute(self.prepared[key], params, execution_profile=profile)

    def execute_raw(self, query: str, params: tuple | list = (), profile: str = EXEC_PROFILE_DEFAULT):
        assert self.session is not None
        return self.session.execute(query, params, execution_profile=profile)

    def close(self) -> None:
        if self.cluster is not None:
            self.cluster.shutdown()
            self.cluster = None
            self.session = None
            self.prepared.clear()
            logger.info("Cassandra cluster cerrado")


cassandra_client = CassandraClient()
