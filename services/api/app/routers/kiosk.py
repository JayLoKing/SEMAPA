"""Kiosk/Tótem público: consulta sin autenticación.

Entrada: numero_contrato (CT-xxx), MAC o CI.
Salida: titular, dirección, estado medidor, consumo, facturas/preavisos.
Cache Redis 60s.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import aio_pika
from cassandra.util import uuid_from_time
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.core.cassandra_client import cassandra_client
from app.core.config import settings
from app.core.redis_client import redis_client
from app.services.tarifa_service import TarifaService, tarifas_desde_filas
from app.services.usd_service import fetch_usd_bob


router = APIRouter()


async def _publish_notify(formato: str, contrato: str, periodo: str) -> bool:
    """Publica un mensaje notify.{formato} en RabbitMQ. True si OK."""
    try:
        conn = await aio_pika.connect_robust(
            host=settings.RABBITMQ_HOST, port=settings.RABBITMQ_PORT,
            login=settings.RABBITMQ_USER, password=settings.RABBITMQ_PASSWORD,
            virtualhost=settings.RABBITMQ_VHOST, timeout=5.0,
        )
        async with conn:
            channel = await conn.channel()
            exch = await channel.declare_exchange("semapa.notifications", aio_pika.ExchangeType.TOPIC, durable=True)
            body = {"formato": formato, "identificador": "contrato", "valor": contrato, "periodo": periodo}
            await exch.publish(
                aio_pika.Message(body=json.dumps(body).encode(),
                                 content_type="application/json",
                                 delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
                routing_key=f"notify.{formato}")
        return True
    except Exception as e:
        logger.warning(f"notify.{formato} no publicado: {e}")
        return False


def _val(v: Any) -> Any:
    if hasattr(v, "hex"):
        return str(v)
    if isinstance(v, Decimal):
        return str(v)
    return v


def _row(r: dict) -> dict:
    return {k: _val(v) for k, v in r.items()}


def _resolver_contrato(q: str) -> dict | None:
    """Resuelve un contrato desde CT-xxx, MAC o CI."""
    qu = q.strip().upper()
    if qu.startswith("CT-"):
        rows = list(cassandra_client.execute("contrato_get", (qu,)))
        if rows:
            return rows[0]
    if ":" in qu:
        rows = list(cassandra_client.execute("contrato_por_mac", (qu,)))
        if rows:
            nc = rows[0]["numero_contrato"]
            full = list(cassandra_client.execute("contrato_get", (nc,)))
            return full[0] if full else rows[0]
    # CI
    for ci in {q, f"{q} CBBA", q.split()[0] if q.split() else q}:
        rows = list(cassandra_client.execute("contratos_por_ci", (ci,)))
        if rows:
            nc = rows[0]["numero_contrato"]
            full = list(cassandra_client.execute("contrato_get", (nc,)))
            return full[0] if full else None
    return None


@router.get("/{identificador}")
async def kiosk(identificador: str):
    """Consulta pública de estado de cuenta para tótem de autoservicio."""
    cache_key = f"kiosk:{identificador.upper()}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    contrato = _resolver_contrato(identificador)
    if not contrato:
        raise HTTPException(404, f"No se encontró contrato para '{identificador}'")

    numero_contrato = contrato["numero_contrato"]
    mac = (contrato.get("medidor_iot") or "").upper()
    catastro = contrato.get("numero_catastro")

    # Dirección desde infraestructura
    direccion = ""
    distrito_id = None
    zona = None
    if catastro:
        infra = list(cassandra_client.execute("infra_get", (catastro,)))
        if infra:
            direccion = infra[0].get("direccion") or ""
            distrito_id = infra[0].get("distrito_id")
            zona = infra[0].get("zona")

    # Estado medidor
    estado_medidor = None
    if mac:
        med = list(cassandra_client.execute("medidor_get", (mac,)))
        if med:
            estado_medidor = med[0].get("estado")

    # Últimas lecturas (consumo)
    lecturas = []
    if mac:
        lrows = list(cassandra_client.execute("lecturas_de_medidor", (mac, 12)))
        for r in lrows:
            lecturas.append({
                "periodo": r.get("periodo"),
                "fecha_hora": _val(r.get("fecha_hora")),
                "lectura_anterior": r.get("lectura_anterior"),
                "lectura_actual": r.get("lectura_actual"),
                "consumo_m3": r.get("consumo_m3"),
                "pagado": r.get("fecha_pago") is not None,
                "fecha_pago": _val(r.get("fecha_pago")),
            })

    # Facturas/preavisos
    facturas = []
    frows = list(cassandra_client.execute_raw(
        "SELECT periodo, monto_bs, monto_usd, consumo_m3, estado FROM facturas "
        "WHERE numero_contrato = %s LIMIT 6", (numero_contrato,)))
    for r in frows:
        facturas.append({
            "periodo": r.get("periodo"),
            "monto_bs": _val(r.get("monto_bs")),
            "monto_usd": _val(r.get("monto_usd")),
            "consumo_m3": _val(r.get("consumo_m3")),
            "estado": r.get("estado"),
        })

    result = {
        "contrato": numero_contrato,
        "mac": mac,
        "titular": {"razon_social": contrato.get("titular_contrato")},
        "ci": contrato.get("ci_titular"),
        "categoria": contrato.get("categoria"),
        "subcategoria": contrato.get("subcategoria"),
        "categoria_tarifa": contrato.get("subcategoria"),
        "direccion": direccion,
        "distrito_id": distrito_id,
        "zona": zona,
        "estado_medidor": estado_medidor,
        "estado_contrato": contrato.get("estado_contrato"),
        "lecturas": lecturas,
        "facturas": facturas,
    }

    await redis_client.set(cache_key, json.dumps(result, default=str), ttl_seconds=60)
    return result


# ============================================================================
# Tótem: pago QR simulado, reclamos/fugas, actualización de contacto
# ============================================================================
class PagoIn(BaseModel):
    numero_contrato: str
    periodo: str
    monto_bs: float | None = None


class ReclamoIn(BaseModel):
    numero_contrato: str
    tipo: str = "RECLAMO"            # FUGA | RECLAMO | OTRO
    descripcion: str = ""


class ContactoIn(BaseModel):
    numero_contrato: str
    telefono: str | None = None
    email: str | None = None


async def _ensure_factura(nc: str, periodo: str) -> Decimal:
    """Genera factura on-the-fly si no existe. Retorna monto_bs final."""
    rows = list(cassandra_client.execute("factura_get", (nc, periodo)))
    if rows:
        return Decimal(str(rows[0]["monto_bs"]))

    # Resuelve contrato → mac + categoria + catastro
    crows = list(cassandra_client.execute("contrato_get", (nc,)))
    if not crows:
        raise HTTPException(404, f"Contrato {nc} no existe")
    c = crows[0]
    mac = (c.get("medidor_iot") or "").upper()
    cat = c.get("subcategoria") or "R3"
    cat_num = c.get("numero_catastro")
    if not mac:
        raise HTTPException(400, f"Contrato {nc} sin medidor")

    # Consumo del periodo
    lrows = list(cassandra_client.execute("lecturas_de_medidor_periodo", (mac, periodo)))
    m3 = Decimal(sum(int(r.get("consumo_m3") or 0) for r in lrows))
    if m3 <= 0:
        # fallback: promedio últimos 6 meses
        last = list(cassandra_client.execute("lecturas_de_medidor", (mac, 6)))
        if last:
            tot = sum(int(r.get("consumo_m3") or 0) for r in last if (r.get("consumo_m3") or 0) > 0)
            m3 = Decimal(max(1, tot // max(1, len(last))))
        else:
            m3 = Decimal("15")  # mínimo razonable

    # Tarifa + cálculo
    trows = list(cassandra_client.execute("list_tarifas"))
    svc = TarifaService(tarifas_desde_filas(trows))
    usd = await fetch_usd_bob()
    tc = Decimal(str(usd["rate"]))
    try:
        f = svc.facturar(cat, m3, tc)
    except ValueError:
        f = svc.facturar("R3", m3, tc)

    # Distrito desde infra
    distrito_id = 0
    if cat_num:
        irows = list(cassandra_client.execute("infra_get", (cat_num,)))
        if irows:
            distrito_id = irows[0].get("distrito_id") or 0

    now = datetime.utcnow()
    cassandra_client.execute("factura_put", (
        nc, periodo, uuid.uuid4(), mac,
        f.consumo_m3, f.monto_usd, f.monto_bs,
        tc, cat, json.dumps(f.to_dict()),
        now, None, "PENDIENTE",
    ))
    cassandra_client.execute("factura_periodo_put", (
        periodo, distrito_id, nc,
        f.monto_bs, f.monto_usd, f.consumo_m3, cat, "PENDIENTE",
    ))
    logger.info(f"Factura auto-generada: {nc}/{periodo} Bs {f.monto_bs}")
    return f.monto_bs


@router.post("/pago")
async def pago_qr(body: PagoIn):
    """Pago QR simulado: auto-genera factura si falta, marca PAGADA, dispara notify."""
    nc = body.numero_contrato.upper()
    now = datetime.utcnow()

    monto_final = await _ensure_factura(nc, body.periodo)
    monto = Decimal(str(body.monto_bs)) if body.monto_bs is not None else monto_final

    cassandra_client.execute_raw(
        "INSERT INTO pagos (numero_contrato, periodo, pago_id, monto_bs, metodo, pagado_en) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (nc, body.periodo, uuid_from_time(now), monto, "QR_SIMULADO", now),
    )
    cassandra_client.execute_raw(
        "UPDATE facturas SET estado='PAGADA', fecha_pago=%s WHERE numero_contrato=%s AND periodo=%s",
        (now, nc, body.periodo),
    )
    await redis_client.set(f"kiosk:{nc}", "", ttl_seconds=1)  # invalida cache
    # Envía comprobante por email/sms/whatsapp (sandbox)
    canales = []
    for f in ("email", "sms", "whatsapp"):
        if await _publish_notify(f, nc, body.periodo):
            canales.append(f)
    return {"ok": True, "numero_contrato": nc, "periodo": body.periodo,
            "qr": f"semapa://pago/{nc}/{body.periodo}", "estado": "PAGADA",
            "notificaciones_enviadas": canales}


@router.post("/reclamo")
async def crear_reclamo(body: ReclamoIn):
    """Registra reclamo o reporte de fuga desde el tótem."""
    nc = body.numero_contrato.upper()
    now = datetime.utcnow()
    rid = uuid_from_time(now)
    cassandra_client.execute_raw(
        "INSERT INTO reclamos (numero_contrato, reclamo_id, tipo, descripcion, creado_en, estado) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (nc, rid, body.tipo.upper(), body.descripcion, now, "ABIERTO"),
    )
    return {"ok": True, "reclamo_id": str(rid), "tipo": body.tipo.upper(), "estado": "ABIERTO"}


class GenIn(BaseModel):
    numero_contrato: str
    periodo: str


@router.post("/factura")
async def generar_factura_publica(body: GenIn):
    """Genera (si falta) la factura del periodo. Pública — útil para PDF/preavisos."""
    nc = body.numero_contrato.upper()
    monto_bs = await _ensure_factura(nc, body.periodo)
    return {"ok": True, "numero_contrato": nc, "periodo": body.periodo,
            "monto_bs": str(monto_bs)}


@router.post("/contacto")
async def actualizar_contacto(body: ContactoIn):
    """Actualiza datos de contacto del usuario (tótem)."""
    nc = body.numero_contrato.upper()
    cassandra_client.execute_raw(
        "INSERT INTO contactos (numero_contrato, telefono, email, actualizado_en) "
        "VALUES (%s, %s, %s, %s)",
        (nc, body.telefono, body.email, datetime.utcnow()),
    )
    return {"ok": True, "numero_contrato": nc}
