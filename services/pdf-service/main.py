"""
SEMAPA PDF Service - Generador de facturas en PDF (ReportLab).

Implementación pendiente (Fase 5):
- GET /pdf?numero_contrato&periodo&formato=rollo|medicarta
- POST /pdf/batch (ZIP con varios PDFs)
- Lee datos de Cassandra (facturas + medidores + personas)
- Aplica reglamento tarifario para mostrar desglose
- Genera QR + código de barras
"""
from fastapi import FastAPI
from loguru import logger

app = FastAPI(title="SEMAPA PDF Service")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "pdf-service"}


@app.get("/pdf")
async def generate_pdf(numero_contrato: int, periodo: str, formato: str = "medicarta"):
    logger.warning("STUB: implementar en Fase 5.")
    return {"message": "not implemented"}
