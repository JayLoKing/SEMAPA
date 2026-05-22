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
            # buscar / kiosk (modelo MAC-céntrico)
            "contrato_get": ps("SELECT * FROM contratos WHERE numero_contrato = ?"),
            "contrato_por_mac": ps("SELECT * FROM contrato_por_mac WHERE medidor_iot = ?"),
            "contratos_por_ci": ps("SELECT * FROM contratos_por_ci WHERE ci_titular = ?"),
            "medidor_get": ps("SELECT * FROM medidores WHERE mac = ?"),
            "infra_get": ps("SELECT * FROM infraestructuras WHERE numero_catastro = ?"),
            "medidores_por_zona": ps("SELECT * FROM medidores_por_zona WHERE distrito_id = ?"),
            # tarifas
            "list_tarifas": ps("SELECT * FROM tarifas"),
            # lecturas
            "lecturas_de_medidor": ps(
                "SELECT * FROM lecturas_por_medidor WHERE mac = ? LIMIT ?"
            ),
            "lecturas_de_medidor_periodo": ps(
                "SELECT * FROM lecturas_por_medidor WHERE mac = ? AND periodo = ?"
            ),
            "lectura_manual_put": ps(
                "INSERT INTO lecturas_manuales (mac, fecha_hora, usuario, lectura_actual, "
                "lat, lon, foto_url) VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            # facturas
            "factura_get": ps("SELECT * FROM facturas WHERE numero_contrato = ? AND periodo = ?"),
            "factura_put": ps(
                "INSERT INTO facturas (numero_contrato, periodo, factura_id, mac, "
                "consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, "
                "fecha_emision, fecha_pago, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            "factura_periodo_put": ps(
                "INSERT INTO facturas_por_periodo (periodo, distrito_id, numero_contrato, monto_bs, "
                "monto_usd, consumo_m3, categoria_tarifa, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
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
