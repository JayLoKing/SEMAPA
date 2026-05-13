"""Genera PDFs de muestra (5 categorías × 2 formatos) en /out.

Uso (dentro del contenedor pdf-service):
    docker run --rm -v ./docs/img/samples:/out semapa-pdf python gen_samples.py
"""
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from main import render_medicarta, render_rollo


SAMPLES = [
    ("R1", 20, "Cliente R1 Casa Litigio"),
    ("R4", 80, "Familia Confortable Cala Cala"),
    ("C",  120, "Tienda Comercial Centro"),
    ("CE", 200, "Hipermercado Sur"),
    ("I",  350, "Industria Petrolera SA"),
]

OUT = Path(os.getenv("OUT_DIR", "/out"))
OUT.mkdir(parents=True, exist_ok=True)


def _mock_desglose(consumo_m3: int, cat: str) -> dict:
    # subtotales placeholder
    tramos = [{"desde_m3": 0, "hasta_m3": 12, "m3_facturados": 12,
               "precio_usd_m3": "0", "subtotal_usd": "8.69"}]
    if consumo_m3 > 12:
        tramos.append({"desde_m3": 13, "hasta_m3": min(25, consumo_m3),
                       "m3_facturados": min(13, consumo_m3 - 12),
                       "precio_usd_m3": "2.58", "subtotal_usd": "33.54"})
    if consumo_m3 > 25:
        tramos.append({"desde_m3": 26, "hasta_m3": min(50, consumo_m3),
                       "m3_facturados": min(25, consumo_m3 - 25),
                       "precio_usd_m3": "2.80", "subtotal_usd": "70.00"})
    return {"tramos": tramos}


def main():
    for cat, m3, nombre in SAMPLES:
        factura = {
            "numero_contrato": 100000000 + m3,
            "periodo": "2025-05",
            "factura_id": uuid4(),
            "medidor_id": uuid4(),
            "consumo_m3": m3,
            "monto_usd": "150.50",
            "monto_bs": "1047.48",
            "tipo_cambio": "6.96",
            "categoria_tarifa": cat,
            "estado": "PENDIENTE",
            "fecha_emision": datetime.utcnow(),
            "desglose": json.dumps(_mock_desglose(m3, cat)),
            "medidor": {"mac": "AB:CD:EF:01:02", "distrito_id": 1, "zona_id": 24},
            "persona": {"tipo": "JURIDICA", "razon_social": nombre, "documento": "1234567"},
            "infraestructura": {"direccion": "Av. Heroínas #123"},
        }
        for fmt, fn in (("medicarta", render_medicarta), ("rollo", render_rollo)):
            data = fn(factura)
            path = OUT / f"sample-{cat}-{fmt}.pdf"
            path.write_bytes(data)
            print(f"✓ {path}")


if __name__ == "__main__":
    main()
