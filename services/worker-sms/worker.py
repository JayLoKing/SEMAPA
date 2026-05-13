"""
SEMAPA Worker SMS - Consume RabbitMQ queue 'notify.sms'.

Implementación pendiente (Fase 6):
- Consume notify.sms
- Mock Twilio: logea el mensaje y simula entrega
- Mensaje:
  "Sr. [Apellido], Semapa te recuerda que su recibo de consumo de agua es de
   Bs [monto_bs]. Por el período [YYYY-MM] usted consumió [m3] m³ de agua."
"""
from loguru import logger


def main():
    logger.info("SEMAPA Worker SMS iniciando...")
    logger.warning("STUB: implementar en Fase 6.")


if __name__ == "__main__":
    main()
