"""
SEMAPA Worker Email - Consume RabbitMQ queue 'notify.email' y envía correos.

Implementación pendiente (Fase 6):
- Conecta a RabbitMQ, consume notify.email
- Resuelve datos del cliente (Cassandra) y factura
- Pide los 2 PDFs (rollo + media carta) al pdf-service
- Arma body:
  "Sr. [Apellido], Semapa te recuerda que su recibo de consumo de agua es de
   Bs [monto_bs]. Por el período [YYYY-MM] usted consumió [m3] m³ de agua."
- Envía vía SMTP a Mailhog (dev) con los 2 PDFs adjuntos.
- 3 reintentos exponenciales, luego DLQ.
"""
from loguru import logger


def main():
    logger.info("SEMAPA Worker Email iniciando...")
    logger.warning("STUB: implementar en Fase 6.")


if __name__ == "__main__":
    main()
