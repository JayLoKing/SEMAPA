"""Lecturas manuales (app móvil) + listado por medidor."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.core.cassandra_client import cassandra_client
from app.core.security import current_user
from app.models.schemas import LecturaManualIn


router = APIRouter()


def _resolve_mac(body: LecturaManualIn) -> str:
    """Devuelve el MAC del medidor a partir de mac o numero_contrato."""
    if body.mac:
        return body.mac.upper()
    if body.numero_contrato:
        rows = list(cassandra_client.execute("contrato_get", (body.numero_contrato.upper(),)))
        if rows and rows[0].get("medidor_iot"):
            return rows[0]["medidor_iot"].upper()
        raise HTTPException(404, "Contrato sin medidor asociado")
    raise HTTPException(400, "Debe enviar mac o numero_contrato")


@router.post("/manual")
async def lectura_manual(body: LecturaManualIn, user: dict = Depends(current_user)):
    mac = _resolve_mac(body)
    ts = datetime.utcnow()

    # 1. Registro en lecturas_manuales
    cassandra_client.execute("lectura_manual_put", (
        mac, ts, user["sub"], body.lectura_actual, body.lat, body.lon, body.foto_url,
    ))

    # 2. También en lecturas_por_medidor (status=2 manual). Calcula consumo vs última.
    periodo = f"{ts.year:04d}-{ts.month:02d}"
    prev = list(cassandra_client.execute("lecturas_de_medidor", (mac, 1)))
    lectura_anterior = prev[0]["lectura_actual"] if prev else body.lectura_actual
    consumo = max(0, body.lectura_actual - lectura_anterior)
    cassandra_client.execute_raw(
        "INSERT INTO lecturas_por_medidor (mac, periodo, fecha_hora, lectura_anterior, "
        "lectura_actual, consumo_m3, radiobase, fecha_pago, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (mac, periodo, ts, lectura_anterior, body.lectura_actual, consumo, None, None, 2),
    )
    return {"ok": True, "mac": mac, "consumo_m3": consumo, "timestamp": ts.isoformat()}


@router.get("/{mac}")
async def lecturas_por_medidor(mac: str, limite: int = 50, _u: dict = Depends(current_user)):
    """Historial de lecturas de un medidor (por MAC)."""
    rows = list(cassandra_client.execute("lecturas_de_medidor", (mac.upper(), limite)))
    return [
        {
            "periodo": r.get("periodo"),
            "fecha_hora": r.get("fecha_hora").isoformat() if r.get("fecha_hora") else None,
            "lectura_anterior": r.get("lectura_anterior"),
            "lectura_actual": r.get("lectura_actual"),
            "consumo_m3": r.get("consumo_m3"),
            "status": r.get("status"),
            "pagado": r.get("fecha_pago") is not None,
        }
        for r in rows
    ]
