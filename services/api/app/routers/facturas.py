"""Facturación / preavisos: generación batch + recuperación."""
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
async def obtener_factura(numero_contrato: str, periodo: str, _u: dict = Depends(current_user)):
    rows = list(cassandra_client.execute("factura_get", (numero_contrato.upper(), periodo)))
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
    """Genera (o regenera) preavisos del periodo a partir de las lecturas reales."""
    if user["rol"] not in ("CONTABILIDAD", "ALCALDIA"):
        raise HTTPException(403, "Rol no autorizado")

    svc = _load_tarifa_service()
    usd = await fetch_usd_bob()
    tipo_cambio = Decimal(str(usd["rate"]))
    now = datetime.utcnow()

    n_ok = 0
    # Recorre contratos activos con medidor; toma consumo del periodo de lecturas.
    contratos = cassandra_client.execute_raw(
        "SELECT numero_contrato, medidor_iot, subcategoria, numero_catastro "
        "FROM contratos LIMIT %s", (limite,), profile="analytics",
    )
    for c in contratos:
        mac = (c.get("medidor_iot") or "").upper()
        if not mac:
            continue
        lecturas = list(cassandra_client.execute("lecturas_de_medidor_periodo", (mac, periodo)))
        if not lecturas:
            continue
        m3 = Decimal(sum(int(l.get("consumo_m3") or 0) for l in lecturas))
        fpago = next((l.get("fecha_pago") for l in lecturas if l.get("fecha_pago")), None)
        cat = c.get("subcategoria") or "R3"
        try:
            factura = svc.facturar(cat, m3, tipo_cambio)
        except ValueError:
            continue

        # distrito desde infra
        distrito_id = 0
        cat_num = c.get("numero_catastro")
        if cat_num:
            infra = list(cassandra_client.execute("infra_get", (cat_num,)))
            if infra:
                distrito_id = infra[0].get("distrito_id") or 0

        estado = "PAGADA" if fpago else "PENDIENTE"
        factura_id = uuid.uuid4()
        cassandra_client.execute("factura_put", (
            c["numero_contrato"], periodo, factura_id, mac,
            factura.consumo_m3, factura.monto_usd, factura.monto_bs,
            tipo_cambio, cat, json.dumps(factura.to_dict()),
            now, fpago, estado,
        ))
        cassandra_client.execute("factura_periodo_put", (
            periodo, distrito_id, c["numero_contrato"],
            factura.monto_bs, factura.monto_usd, factura.consumo_m3, cat, estado,
        ))
        n_ok += 1

    return {"generadas": n_ok, "periodo": periodo, "tipo_cambio": str(tipo_cambio)}
