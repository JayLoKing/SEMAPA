"""Facturación: generación batch + recuperación + PDF redirect."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.cassandra_client import cassandra_client
from app.core.security import current_user
from app.models.schemas import FacturaOut
from app.services.tarifa_service import TarifaService, tarifas_desde_filas
from app.services.usd_service import fetch_usd_bob


router = APIRouter()


def _load_tarifa_service() -> TarifaService:
    rows = list(cassandra_client.execute("list_tarifas"))
    return TarifaService(tarifas_desde_filas(rows))


@router.get("/{numero_contrato}/{periodo}", response_model=FacturaOut)
async def obtener_factura(numero_contrato: int, periodo: str, _u: dict = Depends(current_user)):
    rows = list(cassandra_client.execute("factura_get", (numero_contrato, periodo)))
    if not rows:
        raise HTTPException(404, "Factura no encontrada")
    r = rows[0]
    return FacturaOut(
        numero_contrato=r["numero_contrato"],
        periodo=r["periodo"],
        factura_id=r["factura_id"],
        consumo_m3=str(r["consumo_m3"]),
        monto_usd=str(r["monto_usd"]),
        monto_bs=str(r["monto_bs"]),
        categoria_tarifa=r["categoria_tarifa"],
        estado=r["estado"],
        fecha_emision=r["fecha_emision"],
        desglose=r.get("desglose"),
    )


@router.post("/generar")
async def generar_facturas(
    periodo: str = Query(pattern=r"^\d{4}-\d{2}$"),
    limite: int = Query(100, ge=1, le=10000),
    user: dict = Depends(current_user),
):
    """Genera (o regenera) facturas del periodo. Job batch limitado por seguridad."""
    if user["rol"] not in ("CONTABILIDAD", "ALCALDIA"):
        raise HTTPException(403, "Rol no autorizado")

    svc = _load_tarifa_service()
    usd = await fetch_usd_bob()
    tipo_cambio = Decimal(str(usd["rate"]))
    now = datetime.utcnow()
    year, month = (int(x) for x in periodo.split("-"))
    anio_mes = year * 100 + month

    n_ok = 0
    rows = cassandra_client.execute_raw(
        "SELECT medidor_id, numero_contrato, infraestructura_id, categoria_tarifa, distrito_id "
        "FROM medidores WHERE estado='ACTIVO' ALLOW FILTERING LIMIT %s",
        (limite,),
    )
    for med in rows:
        # Sumar consumo del periodo (litros) → m³
        lecturas = list(cassandra_client.execute("lecturas_de_medidor",
                                                  (med["medidor_id"], anio_mes, 200)))
        litros = sum(int(l.get("consumo_litros") or 0) for l in lecturas)
        m3 = Decimal(litros) / Decimal(1000)
        cat = med["categoria_tarifa"] or "R3"
        try:
            factura = svc.facturar(cat, m3, tipo_cambio)
        except ValueError:
            continue

        factura_id = uuid.uuid4()
        cassandra_client.execute("factura_put", (
            med["numero_contrato"], periodo, factura_id,
            med["medidor_id"], None,
            factura.consumo_m3, factura.monto_usd, factura.monto_bs,
            tipo_cambio, cat, json.dumps(factura.to_dict()),
            now, "PENDIENTE",
        ))
        cassandra_client.execute("factura_periodo_put", (
            periodo, med["distrito_id"], med["numero_contrato"],
            factura.monto_usd, factura.consumo_m3, cat,
        ))
        n_ok += 1

    return {"generadas": n_ok, "periodo": periodo, "tipo_cambio": str(tipo_cambio)}
