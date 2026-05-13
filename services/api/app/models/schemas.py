"""Pydantic schemas (request/response)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============== Auth ==============
class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str
    nombre: str
    email: Optional[str] = None


class UserMe(BaseModel):
    username: str
    rol: str


# ============== USD ==============
class UsdCotizacion(BaseModel):
    rate: float
    source: str
    fetched_at: str


# ============== Buscar ==============
class BusquedaResultado(BaseModel):
    tipo: str
    payload: dict[str, Any]


# ============== Lectura manual (mobile) ==============
class LecturaManualIn(BaseModel):
    medidor_id: Optional[UUID] = None
    mac: Optional[str] = None
    numero_contrato: Optional[int] = None
    lectura_litros: int = Field(ge=0)
    lat: Optional[float] = None
    lon: Optional[float] = None
    foto_url: Optional[str] = None


# ============== Notify ==============
class NotifyIn(BaseModel):
    formato: str = Field(pattern="^(email|sms|whatsapp)$")
    identificador: str = Field(pattern="^(contrato|carnet|mac)$")
    valor: str
    periodo: str = Field(pattern=r"^\d{4}-\d{2}$")


# ============== Facturas ==============
class FacturaOut(BaseModel):
    numero_contrato: int
    periodo: str
    factura_id: UUID
    consumo_m3: str
    monto_usd: str
    monto_bs: str
    categoria_tarifa: str
    estado: str
    fecha_emision: datetime
    desglose: Optional[str] = None
