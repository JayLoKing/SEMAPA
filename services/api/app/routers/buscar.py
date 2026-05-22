"""Buscador unificado: resuelve por contrato (CT-xxx) / MAC / CI."""
from fastapi import APIRouter, Depends, Query

from app.core.cassandra_client import cassandra_client
from app.core.security import current_user


router = APIRouter()


def _serialize(row: dict) -> dict:
    return {k: (str(v) if hasattr(v, "hex") else v) for k, v in row.items()}


@router.get("")
async def buscar(q: str = Query(min_length=2), _u: dict = Depends(current_user)):
    """Heurística: CT-* → contrato; con `:` → MAC; sólo dígitos → CI."""
    q = q.strip()
    results: list[dict] = []

    qu = q.upper()

    # Contrato CT-00000001
    if qu.startswith("CT-"):
        rows = list(cassandra_client.execute("contrato_get", (qu,)))
        results.extend({"tipo": "contrato", "payload": _serialize(r)} for r in rows)

    # MAC AB:CD:...
    if ":" in q:
        rows = list(cassandra_client.execute("contrato_por_mac", (qu,)))
        results.extend({"tipo": "medidor", "payload": _serialize(r)} for r in rows)
        med = list(cassandra_client.execute("medidor_get", (qu,)))
        results.extend({"tipo": "medidor_detalle", "payload": _serialize(r)} for r in med)

    # CI (dígitos, posiblemente con ' CBBA')
    if q[0].isdigit():
        # CI suele venir como "5922807 CBBA"; probamos tal cual y variantes
        for ci in {q, f"{q} CBBA", q.split()[0]}:
            rows = list(cassandra_client.execute("contratos_por_ci", (ci,)))
            results.extend({"tipo": "contrato", "payload": _serialize(r)} for r in rows)
            if rows:
                break

    return {"q": q, "count": len(results), "results": results[:50]}
