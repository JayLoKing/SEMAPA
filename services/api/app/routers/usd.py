"""USD cotización endpoint."""
from fastapi import APIRouter

from app.models.schemas import UsdCotizacion
from app.services.usd_service import fetch_usd_bob


router = APIRouter()


@router.get("/cotizacion", response_model=UsdCotizacion)
async def cotizacion():
    return await fetch_usd_bob()
