"""Detección de anomalías: lecturas con error y morosos.

Endpoints protegidos — requieren autenticación.
  GET /api/v1/anomalias              → lecturas ERROR + consumo excesivo
  GET /api/v1/anomalias/morosos      → contratos con facturas PENDIENTE vencidas
"""
from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.cassandra_client import cassandra_client
from app.core.redis_client import redis_client
from app.core.security import current_user


router = APIRouter()

_UMBRAL_CONSUMO_LITROS = 50_000  # litros: umbral para anomalía de consumo excesivo


def _serialize_value(v: Any) -> Any:
    """Convierte tipos especiales de Cassandra a tipos JSON-serializables."""
    if hasattr(v, "hex"):        # UUID
        return str(v)
    if isinstance(v, Decimal):
        return str(v)
    return v


# ----------------------------------------------------------------------------
# GET /anomalias
# ----------------------------------------------------------------------------
@router.get("")
async def anomalias(
    limite: int = Query(100, ge=1, le=5000),
    umbral_factor: float = Query(3.0, ge=1.0, le=100.0),
    _u: dict = Depends(current_user),
):
    """Devuelve lecturas con estado ERROR y lecturas con consumo anómalamente alto."""
    umbral_litros = int(_UMBRAL_CONSUMO_LITROS * umbral_factor)
    result: list[dict] = []

    # Lecturas con status de error (status >= 3: errores IoT; status=9: anomalía ingestor)
    # Columnas reales: medidor_id, anio_mes, fecha_hora, gateway_id, lectura_litros, consumo_litros, status
    error_rows = list(
        cassandra_client.execute_raw(
            f"SELECT medidor_id, consumo_litros, fecha_hora, status "
            f"FROM lecturas_por_medidor WHERE status >= 3 ALLOW FILTERING LIMIT {limite}",
            profile="analytics",
        )
    )
    for r in error_rows:
        tipo = "ANOMALIA_CONSUMO" if r.get("status") == 9 else "ERROR_SENSOR"
        result.append(
            {
                "medidor_id": _serialize_value(r.get("medidor_id")),
                "consumo_litros": r.get("consumo_litros"),
                "leido_en": _serialize_value(r.get("fecha_hora")),
                "estado": f"STATUS_{r.get('status', '?')}",
                "tipo_anomalia": tipo,
            }
        )

    # Lecturas con consumo excesivo (status normal pero delta enorme)
    excesivo_rows = list(
        cassandra_client.execute_raw(
            f"SELECT medidor_id, consumo_litros, fecha_hora, status "
            f"FROM lecturas_por_medidor WHERE consumo_litros > {umbral_litros} "
            f"AND status < 3 ALLOW FILTERING LIMIT {limite}",
            profile="analytics",
        )
    )
    for r in excesivo_rows:
        consumo = r.get("consumo_litros") or 0
        result.append(
            {
                "medidor_id": _serialize_value(r.get("medidor_id")),
                "consumo_litros": consumo,
                "leido_en": _serialize_value(r.get("fecha_hora")),
                "estado": f"STATUS_{r.get('status', '?')}",
                "tipo_anomalia": "CONSUMO_EXCESIVO",
            }
        )

    return {"total": len(result), "umbral_litros": umbral_litros, "anomalias": result}


# ----------------------------------------------------------------------------
# GET /anomalias/morosos
# ----------------------------------------------------------------------------
@router.get("/morosos")
async def morosos(
    limite: int = Query(200, ge=1, le=10000),
    meses: int = Query(3, ge=1, le=24),
    _u: dict = Depends(current_user),
):
    """Contratos con facturas PENDIENTE agrupados por contrato, ordenados por vencimientos."""
    cache_key = f"anomalias:morosos:{limite}:{meses}"

    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    pendientes = list(
        cassandra_client.execute_raw(
            f"SELECT numero_contrato, periodo, monto_bs, estado "
            f"FROM facturas WHERE estado='PENDIENTE' ALLOW FILTERING LIMIT {limite}",
            profile="analytics",
        )
    )

    # Agrupar por contrato
    por_contrato: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"monto_total_bs": Decimal("0"), "periodos": []}
    )
    for r in pendientes:
        nc = r["numero_contrato"]
        monto = r.get("monto_bs") or Decimal("0")
        periodo = r.get("periodo")
        por_contrato[nc]["monto_total_bs"] += monto if isinstance(monto, Decimal) else Decimal(str(monto or 0))
        por_contrato[nc]["periodos"].append(periodo)

    result = sorted(
        [
            {
                "numero_contrato": nc,
                "periodos_vencidos": len(v["periodos"]),
                "monto_total_bs": str(v["monto_total_bs"]),
                "periodos": sorted(p for p in v["periodos"] if p is not None),
            }
            for nc, v in por_contrato.items()
            if len(v["periodos"]) >= meses
        ],
        key=lambda x: -x["periodos_vencidos"],
    )

    payload = {"total": len(result), "morosos": result}

    await redis_client.set(cache_key, json.dumps(payload, default=str), ttl_seconds=120)

    return payload
