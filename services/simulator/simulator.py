"""
SEMAPA Simulator LoRaWAN - Genera archivos .txt simulando lecturas de medidores.

Implementación pendiente (Fase 3):
- Lee lista de medidores desde Cassandra
- Cada hora genera archivos en /lora-data/{gateway}/{YYYY-MM-DD-HH}/{mac}.txt
- 0.5% con status de error, 0.07% duplicados
- Expone endpoint /simulate/burst para disparos manuales
"""
from loguru import logger


def main():
    logger.info("SEMAPA Simulator iniciando...")
    logger.warning("STUB: implementar en Fase 3.")


if __name__ == "__main__":
    main()
