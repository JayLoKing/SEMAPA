"""SEMAPA - FastAPI main entry point.

Inicializa el cluster Cassandra como singleton, prepara statements,
configura CORS, middlewares de logs y rutas.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.cassandra_client import cassandra_client
from app.core.config import settings
from app.core.middleware import JsonLogMiddleware, RateLimitMiddleware
from app.core.redis_client import redis_client
from app.routers import (anomalias, auth, buscar, consultas, dashboard,
                         facturas, kiosk, lecturas, notify, usd)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando SEMAPA API...")
    try:
        cassandra_client.connect()
        cassandra_client.prepare_statements()
    except Exception as e:
        logger.error(f"Cassandra no disponible al startup: {e}")
    try:
        await redis_client.connect()
    except Exception as e:
        logger.error(f"Redis no disponible al startup: {e}")
    logger.info("SEMAPA API lista.")
    yield
    logger.info("Cerrando SEMAPA API...")
    cassandra_client.close()
    await redis_client.close()


app = FastAPI(
    title="SEMAPA API",
    description="Sistema de gestión inteligente de agua potable - Cochabamba",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.API_CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JsonLogMiddleware)
app.add_middleware(RateLimitMiddleware, limit_per_min=200)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "semapa-api"}


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(consultas.router, prefix="/api/v1/consultas", tags=["consultas"])
app.include_router(facturas.router, prefix="/api/v1/facturas", tags=["facturas"])
app.include_router(notify.router, prefix="/api/v1/notify", tags=["notify"])
app.include_router(usd.router, prefix="/api/v1/usd", tags=["usd"])
app.include_router(buscar.router, prefix="/api/v1/buscar", tags=["buscar"])
app.include_router(lecturas.router, prefix="/api/v1/lecturas", tags=["lecturas"])
app.include_router(kiosk.router, prefix="/api/v1/kiosk", tags=["kiosk"])
app.include_router(anomalias.router, prefix="/api/v1/anomalias", tags=["anomalias"])
