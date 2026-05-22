"""SEMAPA — PDF Service (ReportLab).

Endpoints:
  GET  /health
  GET  /pdf?numero_contrato=&periodo=&formato=rollo|medicarta
  POST /pdf/batch   — body: {"items": [{"numero_contrato":..,"periodo":..,"formato":..}, ...]}
                      respuesta: application/zip

Formatos:
  - `medicarta`  : A5 (148×210 mm)
  - `rollo`      : 80mm × variable (impresora térmica)

Datos:
  - Lee `facturas` desde Cassandra. Si la factura tiene `desglose` (JSON), lo
    renderiza. Sino, calcula desglose on-the-fly con TarifaService.
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import datetime
from decimal import Decimal
from typing import Literal

import qrcode
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from loguru import logger
from pydantic import BaseModel
from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)


CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra-1,cassandra-2").split(",")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "semapa")
CASSANDRA_USER = os.getenv("CASSANDRA_USER", "")
CASSANDRA_PASSWORD = os.getenv("CASSANDRA_PASSWORD", "")

_cluster: Cluster | None = None
_session = None


app = FastAPI(title="SEMAPA PDF Service", version="1.0.0")


# ============================================================================
# Cassandra
# ============================================================================
@app.on_event("startup")
async def startup():
    global _cluster, _session
    auth = PlainTextAuthProvider(CASSANDRA_USER, CASSANDRA_PASSWORD) if CASSANDRA_USER else None
    for i in range(30):
        try:
            _cluster = Cluster(contact_points=CASSANDRA_HOSTS, port=CASSANDRA_PORT,
                               auth_provider=auth, protocol_version=5)
            _session = _cluster.connect(CASSANDRA_KEYSPACE)
            _session.row_factory = dict_factory
            logger.info("PDF service: Cassandra conectado")
            return
        except Exception as e:
            logger.warning(f"Cassandra retry {i+1}/30: {e}")
            import asyncio
            await asyncio.sleep(5)
    logger.error("Cassandra no disponible al startup")


@app.on_event("shutdown")
async def shutdown():
    if _cluster:
        _cluster.shutdown()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pdf-service"}


# ============================================================================
# Carga de factura
# ============================================================================
def _load_factura(numero_contrato: str, periodo: str) -> dict:
    if _session is None:
        raise HTTPException(503, "Cassandra no conectado")
    numero_contrato = numero_contrato.upper()
    rows = list(_session.execute(
        "SELECT * FROM facturas WHERE numero_contrato = %s AND periodo = %s",
        (numero_contrato, periodo),
    ))
    if not rows:
        raise HTTPException(404, "Factura no encontrada")
    factura = rows[0]
    # enrichment: contrato (titular/ci/catastro) → infra (dirección/zona)
    cs = list(_session.execute(
        "SELECT * FROM contratos WHERE numero_contrato = %s", (numero_contrato,)))
    if cs:
        c = cs[0]
        factura["titular"] = c.get("titular_contrato")
        factura["documento"] = c.get("ci_titular")
        factura["mac"] = factura.get("mac") or c.get("medidor_iot")
        factura["categoria"] = c.get("categoria")
        if c.get("numero_catastro"):
            inf = list(_session.execute(
                "SELECT * FROM infraestructuras WHERE numero_catastro = %s", (c["numero_catastro"],)))
            if inf:
                factura["infraestructura"] = inf[0]
    return factura


# ============================================================================
# Helpers UI
# ============================================================================
def _qr_image(data: str) -> io.BytesIO:
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _cliente_nombre(factura: dict) -> str:
    return factura.get("titular") or "Cliente SEMAPA"


# ============================================================================
# Formato media carta (A5)
# ============================================================================
def render_medicarta(factura: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A5,
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>SEMAPA — Servicio Municipal de Agua Potable</b>",
                           styles["Title"]))
    story.append(Paragraph("Factura de consumo de agua potable", styles["Heading4"]))
    story.append(Spacer(1, 6))

    infra = factura.get("infraestructura") or {}

    tabla_cliente = [
        ["Cliente:", _cliente_nombre(factura)],
        ["Documento:", factura.get("documento", "-")],
        ["Contrato:", str(factura["numero_contrato"])],
        ["Medidor MAC:", factura.get("mac", "-")],
        ["Dirección:", infra.get("direccion", "-")],
        ["Distrito / Zona:", f"{infra.get('distrito_id', '-')} / {infra.get('zona', '-')}"],
        ["Período:", factura["periodo"]],
        ["Categoría:", factura.get("categoria_tarifa", "-")],
        ["Emitida:", factura.get("fecha_emision").strftime("%Y-%m-%d %H:%M") if factura.get("fecha_emision") else "-"],
    ]
    t = Table(tabla_cliente, colWidths=[35 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

    # Desglose tramos
    desglose = []
    if factura.get("desglose"):
        try:
            desglose = json.loads(factura["desglose"]).get("tramos", [])
        except Exception:
            pass
    data = [["Tramo", "m³", "USD/m³", "Subtotal USD"]]
    for tr in desglose:
        data.append([
            f"{tr['desde_m3']}–{tr['hasta_m3']}",
            tr["m3_facturados"],
            tr["precio_usd_m3"],
            tr["subtotal_usd"],
        ])
    t2 = Table(data, colWidths=[30 * mm, 25 * mm, 30 * mm, 35 * mm])
    t2.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    story.append(t2)
    story.append(Spacer(1, 8))

    totales = [
        ["Consumo (m³):", str(factura["consumo_m3"])],
        ["Tipo de cambio:", str(factura.get("tipo_cambio", "-"))],
        ["TOTAL USD:", str(factura["monto_usd"])],
        ["TOTAL Bs.:", str(factura["monto_bs"])],
    ]
    t3 = Table(totales, colWidths=[60 * mm, 65 * mm])
    t3.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, -2), (-1, -1), colors.HexColor("#d1e7dd")),
    ]))
    story.append(t3)

    doc.build(story, onFirstPage=lambda c, _: _draw_medicarta_qr(c, factura),
              onLaterPages=lambda c, _: _draw_medicarta_qr(c, factura))
    return buf.getvalue()


def _draw_medicarta_qr(c: canvas.Canvas, factura: dict) -> None:
    qr_data = f"semapa://factura/{factura['numero_contrato']}/{factura['periodo']}"
    qr = _qr_image(qr_data)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(qr), 110 * mm, 175 * mm, width=30 * mm, height=30 * mm)
    barcode = code128.Code128(str(factura["numero_contrato"]), barWidth=0.4 * mm, barHeight=10 * mm)
    barcode.drawOn(c, 12 * mm, 10 * mm)


# ============================================================================
# Formato rollo térmico 80 mm
# ============================================================================
def render_rollo(factura: dict) -> bytes:
    width = 55 * mm   # rollo térmico 55 mm (kioscos / tótems)
    # Altura dinámica: 110 mm base + ~6 mm por tramo
    desglose = []
    if factura.get("desglose"):
        try:
            desglose = json.loads(factura["desglose"]).get("tramos", [])
        except Exception:
            pass
    height = (110 + max(0, len(desglose)) * 6 + 30) * mm

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    y = height - 10 * mm

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, y, "SEMAPA — RECIBO")
    y -= 5 * mm
    c.setFont("Helvetica", 7)
    c.drawCentredString(width / 2, y, "Servicio Municipal de Agua Potable")
    y -= 6 * mm

    c.setFont("Helvetica", 7)
    for label, value in [
        ("Cliente", _cliente_nombre(factura)[:28]),
        ("Doc", factura.get("documento", "-")),
        ("Contrato", str(factura["numero_contrato"])),
        ("MAC", factura.get("mac", "-")),
        ("Periodo", factura["periodo"]),
        ("Cat", factura.get("categoria_tarifa", "-")),
    ]:
        c.drawString(3 * mm, y, f"{label}:")
        c.drawRightString(width - 3 * mm, y, str(value))
        y -= 4.5 * mm

    y -= 2 * mm
    c.line(4 * mm, y, width - 4 * mm, y)
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 8)
    c.drawString(4 * mm, y, "Tramo")
    c.drawCentredString(width / 2, y, "m³")
    c.drawRightString(width - 4 * mm, y, "USD")
    y -= 4 * mm
    c.setFont("Helvetica", 8)
    for tr in desglose:
        c.drawString(4 * mm, y, f"{tr['desde_m3']}-{tr['hasta_m3']}")
        c.drawCentredString(width / 2, y, str(tr["m3_facturados"]))
        c.drawRightString(width - 4 * mm, y, str(tr["subtotal_usd"]))
        y -= 4 * mm

    y -= 1 * mm
    c.line(4 * mm, y, width - 4 * mm, y)
    y -= 5 * mm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(4 * mm, y, "Total USD")
    c.drawRightString(width - 4 * mm, y, str(factura["monto_usd"]))
    y -= 4.5 * mm
    c.drawString(4 * mm, y, "Total Bs.")
    c.drawRightString(width - 4 * mm, y, str(factura["monto_bs"]))
    y -= 8 * mm

    # QR
    from reportlab.lib.utils import ImageReader
    qr = _qr_image(f"semapa://factura/{factura['numero_contrato']}/{factura['periodo']}")
    c.drawImage(ImageReader(qr), (width - 25 * mm) / 2, y - 25 * mm, width=25 * mm, height=25 * mm)
    y -= 28 * mm

    c.setFont("Helvetica-Oblique", 6)
    c.drawCentredString(width / 2, y, "Gracias por su pago puntual.")
    y -= 3 * mm
    c.drawCentredString(width / 2, y, "SEMAPA Cochabamba — Bolivia")

    c.showPage()
    c.save()
    return buf.getvalue()


# ============================================================================
# Endpoints
# ============================================================================
@app.get("/pdf")
async def generate_pdf(
    numero_contrato: str,
    periodo: str = Query(pattern=r"^\d{4}-\d{2}$"),
    formato: Literal["rollo", "medicarta"] = "medicarta",
):
    factura = _load_factura(numero_contrato, periodo)
    pdf = render_medicarta(factura) if formato == "medicarta" else render_rollo(factura)
    fname = f"semapa-{numero_contrato}-{periodo}-{formato}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{fname}"'})


class BatchItem(BaseModel):
    numero_contrato: str
    periodo: str
    formato: Literal["rollo", "medicarta"] = "medicarta"


class BatchRequest(BaseModel):
    items: list[BatchItem]


@app.post("/pdf/batch")
async def batch(req: BatchRequest):
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as z:
        for item in req.items:
            try:
                factura = _load_factura(item.numero_contrato, item.periodo)
                pdf = (render_medicarta(factura) if item.formato == "medicarta"
                       else render_rollo(factura))
                z.writestr(f"{item.numero_contrato}-{item.periodo}-{item.formato}.pdf", pdf)
            except HTTPException as e:
                z.writestr(
                    f"ERROR-{item.numero_contrato}-{item.periodo}.txt",
                    f"{e.status_code}: {e.detail}",
                )
    zip_buf.seek(0)
    return StreamingResponse(
        zip_buf, media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="semapa-facturas.zip"'},
    )
