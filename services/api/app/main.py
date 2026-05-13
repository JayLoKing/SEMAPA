"""
SEMAPA - FastAPI main entry point.

Inicializa el cluster Cassandra como singleton, prepara statements,
configura CORS, middlewares de logs y rutas.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
# from app.core.cassandra_client import cassandra_client
# from app.core.redis_client import redis_client
# from app.routers import auth, dashboard, consultas, facturas, notify, usd, buscar


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa recursos al startup y los libera al shutdown."""
    logger.info("Iniciando SEMAPA API...")
    # await cassandra_client.connect()
    # await redis_client.connect()
    # cassandra_client.prepare_statements()
    logger.info("SEMAPA API lista.")
    yield
    logger.info("Cerrando SEMAPA API...")
    # await cassandra_client.close()
    # await redis_client.close()


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


@app.get("/health")
async def health():
    """Healthcheck endpoint."""
    return {"status": "ok", "service": "semapa-api"}


# Routers - descomentar conforme se implementen
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
# app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
# app.include_router(consultas.router, prefix="/api/v1/consultas", tags=["consultas"])
# app.include_router(facturas.router, prefix="/api/v1/facturas", tags=["facturas"])
# app.include_router(notify.router, prefix="/api/v1/notify", tags=["notify"])
# app.include_router(usd.router, prefix="/api/v1/usd", tags=["usd"])
# app.include_router(buscar.router, prefix="/api/v1/buscar", tags=["buscar"])
