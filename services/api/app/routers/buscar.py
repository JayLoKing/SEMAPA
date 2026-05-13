"""Buscador unificado: resuelve por contrato / MAC / serie / documento."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.cassandra_client import cassandra_client
from app.core.security import current_user


router = APIRouter()


def _serialize(row: dict) -> dict:
    return {k: (str(v) if hasattr(v, "hex") else v) for k, v in row.items()}


@router.get("")
async def buscar(q: str = Query(min_length=2), _u: dict = Depends(current_user)):
    """Heurística: numérico → contrato; con `:` → MAC; otro → documento o serie."""
    q = q.strip()
    results: list[dict] = []

    if q.isdigit():
        rows = list(cassandra_client.execute("find_medidor_by_contrato", (int(q),)))
        results.extend({"tipo": "medidor", "payload": _serialize(r)} for r in rows)
        rows = list(cassandra_client.execute("find_persona_by_doc", (q,)))
        results.extend({"tipo": "persona", "payload": _serialize(r)} for r in rows)

    if ":" in q:
        rows = list(cassandra_client.execute("find_medidor_by_mac", (q.upper(),)))
        results.extend({"tipo": "medidor", "payload": _serialize(r)} for r in rows)

    if q.upper().startswith("SN="):
        rows = list(cassandra_client.execute("find_medidor_by_serie", (q.upper(),)))
        results.extend({"tipo": "medidor", "payload": _serialize(r)} for r in rows)

    return {"q": q, "count": len(results), "results": results[:50]}
