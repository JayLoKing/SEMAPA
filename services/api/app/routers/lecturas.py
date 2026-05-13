"""Lecturas manuales (app móvil) + listado por medidor."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.core.cassandra_client import cassandra_client
from app.core.security import current_user
from app.models.schemas import LecturaManualIn


router = APIRouter()


def _resolve_medidor(body: LecturaManualIn) -> dict:
    if body.medidor_id:
        rows = list(cassandra_client.execute_raw(
            "SELECT * FROM medidores WHERE medidor_id = %s", (body.medidor_id,)
        ))
    elif body.mac:
        rows = list(cassandra_client.execute("find_medidor_by_mac", (body.mac.upper(),)))
    elif body.numero_contrato:
        rows = list(cassandra_client.execute("find_medidor_by_contrato", (body.numero_contrato,)))
    else:
        raise HTTPException(400, "Debe enviar medidor_id, mac o numero_contrato")
    if not rows:
        raise HTTPException(404, "Medidor no encontrado")
    return rows[0]


@router.post("/manual")
async def lectura_manual(body: LecturaManualIn, user: dict = Depends(current_user)):
    medidor = _resolve_medidor(body)
    ts = datetime.utcnow()
    cassandra_client.execute("lectura_manual_put", (
        medidor["medidor_id"], ts, user["sub"],
        body.lectura_litros, body.lat, body.lon, body.foto_url,
    ))
    # También insertar en lecturas_por_medidor con status=2 (manual)
    anio_mes = ts.year * 100 + ts.month
    cassandra_client.execute_raw(
        "INSERT INTO lecturas_por_medidor (medidor_id, anio_mes, fecha_hora, gateway_id, "
        "lectura_litros, consumo_litros, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (medidor["medidor_id"], anio_mes, ts, medidor.get("gateway_id"),
         body.lectura_litros, 0, 2),
    )
    return {"ok": True, "medidor_id": str(medidor["medidor_id"]), "timestamp": ts.isoformat()}
