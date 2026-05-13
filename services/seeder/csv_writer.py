"""CSV writers para data/seeds/.

Idempotente: sobreescribe los CSVs en cada ejecución.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from loguru import logger


def write_csv(path: Path, header: list[str], rows: Iterable[tuple]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
            n += 1
    logger.info(f"CSV escrito: {path} ({n} filas)")
    return n
