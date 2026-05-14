"""Kiosk público: consulta de contrato sin autenticación.

Endpoint pensado para pantallas de autoservicio en oficinas SEMAPA.
Devuelve titular, dirección, estado del medidor y últimas 6 facturas.
Resultado cacheado en Redis 60 segundos (clave kiosk:{contrato}).
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.cassandra_client import cassandra_client
from app.core.redis_client import redis_client


router = APIRouter()


def _serialize_value(v: Any) -> Any:
    """Convierte tipos especiales de Cassandra a tipos JSON-serializables."""
    if hasattr(v, "hex"):          # UUID
        return str(v)
    if isinstance(v, Decimal):
        return str(v)
    return v


def _serialize_row(row: dict) -> dict:
    return {k: _serialize_value(v) for k, v in row.items()}


@router.get("/{contrato}")
async def kiosk_contrato(contrato: int):
    """Devuelve información resumida del contrato para pantallas de autoservicio."""
    cache_key = f"kiosk:{contrato}"

    # Intentar desde cache Redis
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # 1. Datos del medidor (numero_contrato es la partition key o secondary index)
    medidor_rows = list(
        cassandra_client.execute("find_medidor_by_contrato", (contrato,))
    )
    if not medidor_rows:
        raise HTTPException(status_code=404, detail=f"Contrato {contrato} no encontrado")

    medidor = medidor_rows[0]
    infraestructura_id = medidor.get("infraestructura_id")
    estado_medidor = medidor.get("estado")
    categoria_tarifa = medidor.get("categoria_tarifa")

    # 2. Datos de infraestructura (dirección) — parameterized para UUID seguro
    direccion = ""
    persona_id = None
    if infraestructura_id is not None:
        infra_rows = list(
            cassandra_client.execute_raw(
                "SELECT * FROM infraestructuras WHERE infraestructura_id = %s",
                (infraestructura_id,),
            )
        )
        if infra_rows:
            infra = infra_rows[0]
            direccion = infra.get("direccion") or infra.get("descripcion") or ""
            persona_id = infra.get("persona_id")

    # 3. Datos de la persona titular
    titular: dict[str, Any] = {}
    if persona_id is not None:
        persona_rows = list(
            cassandra_client.execute_raw(
                "SELECT * FROM personas WHERE persona_id = %s",
                (persona_id,),
            )
        )
        if persona_rows:
            persona = persona_rows[0]
            razon_social = persona.get("razon_social")
            if razon_social:
                titular = {"razon_social": razon_social}
            else:
                titular = {
                    "nombre": persona.get("nombre", ""),
                    "apellido": persona.get("apellidos", ""),
                }

    # 4. Últimas 6 facturas (numero_contrato es partition key de facturas)
    factura_rows = list(
        cassandra_client.execute_raw(
            "SELECT periodo, monto_bs, monto_usd, consumo_m3, estado FROM facturas "
            "WHERE numero_contrato = %s LIMIT 6",
            (contrato,),
        )
    )
    facturas = [
        {
            "periodo": r.get("periodo"),
            "monto_bs": _serialize_value(r.get("monto_bs")),
            "monto_usd": _serialize_value(r.get("monto_usd")),
            "consumo_m3": _serialize_value(r.get("consumo_m3")),
            "estado": r.get("estado"),
        }
        for r in factura_rows
    ]

    result = {
        "contrato": contrato,
        "titular": titular,
        "direccion": direccion,
        "categoria_tarifa": categoria_tarifa,
        "estado_medidor": estado_medidor,
        "facturas": facturas,
    }

    # Guardar en Redis por 60 segundos
    await redis_client.set(cache_key, json.dumps(result, default=str), ttl_seconds=60)

    return result
