"""
SEMAPA Ingestor - Observa /lora-data y persiste lecturas en Cassandra.

Implementación pendiente (Fase 3):
- watchdog.observers.Observer en INGESTOR_WATCH_DIR
- Por cada archivo .txt nuevo: parsea CSV inline, deduplica con Redis
  (key = mac:fecha_hora, TTL 24h), inserta en lecturas_por_medidor +
  lecturas_por_zona_dia + lecturas_raw.
- Usar execute_concurrent_with_args con prepared statements.
"""
from loguru import logger


def main():
    logger.info("SEMAPA Ingestor iniciando...")
    logger.warning("STUB: implementar en Fase 3.")
    # TODO: Implementar watcher


if __name__ == "__main__":
    main()
