"""SEMAPA — Worker SMS (Twilio).

Consume `notify.sms` desde RabbitMQ y envía vía Twilio SMS API.

Variables de entorno:
  SMS_PROVIDER                 twilio | mock  (default twilio)
  TWILIO_ACCOUNT_SID           AC...
  TWILIO_AUTH_TOKEN
  TWILIO_MESSAGING_SERVICE_SID MG... (preferido sobre TWILIO_SMS_FROM)
  TWILIO_SMS_FROM              +1XXXXXXXXXX (fallback)

Nota Twilio trial:
  - Los receptores deben estar verificados en la consola.
  - Máximo 5 pre-verified recipients.
"""
from __future__ import annotations

import json
import os
import time

import pika
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from loguru import logger
from twilio.rest import Client as TwilioClient


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "semapa")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "semapa")

CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra-1,cassandra-2").split(",")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "semapa")
CASSANDRA_USER = os.getenv("CASSANDRA_USER", "")
CASSANDRA_PASSWORD = os.getenv("CASSANDRA_PASSWORD", "")

QUEUE = "notify.sms"
MAX_RETRIES = 3

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "twilio").lower()
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_MSG_SVC = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "")
TWILIO_FROM = os.getenv("TWILIO_SMS_FROM", "")

_twilio: TwilioClient | None = None
if SMS_PROVIDER == "twilio" and TWILIO_SID and TWILIO_TOKEN:
    _twilio = TwilioClient(TWILIO_SID, TWILIO_TOKEN)


def connect_cassandra():
    auth = PlainTextAuthProvider(CASSANDRA_USER, CASSANDRA_PASSWORD) if CASSANDRA_USER else None
    for i in range(30):
        try:
            c = Cluster(CASSANDRA_HOSTS, port=CASSANDRA_PORT, auth_provider=auth, protocol_version=5)
            s = c.connect(CASSANDRA_KEYSPACE)
            s.row_factory = dict_factory
            return c, s
        except Exception as e:
            logger.warning(f"Cassandra retry {i+1}/30: {e}")
            time.sleep(5)
    raise RuntimeError("Cassandra no disponible")


def resolve_contrato(session, identificador, valor):
    if identificador == "contrato":
        return int(valor)
    if identificador == "mac":
        rows = list(session.execute("SELECT numero_contrato FROM medidores WHERE mac = %s", (valor.upper(),)))
        return rows[0]["numero_contrato"] if rows else None
    if identificador == "carnet":
        rows = list(session.execute("SELECT persona_id FROM personas WHERE documento = %s", (valor,)))
        if not rows:
            return None
        infs = list(session.execute("SELECT infraestructura_id FROM infraestructuras WHERE persona_id = %s", (rows[0]["persona_id"],)))
        for inf in infs:
            meds = list(session.execute(
                "SELECT numero_contrato FROM medidores WHERE infraestructura_id = %s ALLOW FILTERING",
                (inf["infraestructura_id"],)))
            if meds:
                return meds[0]["numero_contrato"]
    return None


def load_data(session, contrato, periodo):
    factura = list(session.execute(
        "SELECT monto_bs, consumo_m3 FROM facturas WHERE numero_contrato = %s AND periodo = %s",
        (contrato, periodo)))
    if not factura:
        return None
    medidor = list(session.execute("SELECT infraestructura_id FROM medidores WHERE numero_contrato = %s", (contrato,)))
    telefono = None
    apellido = "Cliente"
    if medidor:
        inf = list(session.execute("SELECT persona_id FROM infraestructuras WHERE infraestructura_id = %s",
                                   (medidor[0]["infraestructura_id"],)))
        if inf:
            pers = list(session.execute(
                "SELECT telefono, apellidos, razon_social, tipo FROM personas WHERE persona_id = %s",
                (inf[0]["persona_id"],)))
            if pers:
                p = pers[0]
                telefono = p.get("telefono")
                apellido = p.get("razon_social") if p.get("tipo") == "JURIDICA" else p.get("apellidos")
    return {"factura": factura[0], "telefono": telefono, "apellido": apellido}


def _normalize_phone_e164(tel: str) -> str:
    """Convierte teléfono boliviano a E.164 (+591XXXXXXXX)."""
    tel = tel.strip().replace(" ", "").replace("-", "")
    if tel.startswith("+"):
        return tel
    if len(tel) == 8 and tel.isdigit():
        return f"+591{tel}"
    return f"+{tel}" if tel.isdigit() else tel


def send_sms_twilio(telefono: str, body: str):
    if _twilio is None:
        raise RuntimeError("Twilio no configurado (revisa TWILIO_ACCOUNT_SID / AUTH_TOKEN)")
    to = _normalize_phone_e164(telefono)
    kwargs: dict = {"to": to, "body": body}
    if TWILIO_MSG_SVC:
        kwargs["messaging_service_sid"] = TWILIO_MSG_SVC
    elif TWILIO_FROM:
        kwargs["from_"] = TWILIO_FROM
    else:
        raise RuntimeError("Falta TWILIO_MESSAGING_SERVICE_SID o TWILIO_SMS_FROM")
    msg = _twilio.messages.create(**kwargs)
    logger.info(f"📱 SMS Twilio sid={msg.sid} → {to}: {body[:60]}...")


def send_sms_mock(telefono: str, body: str):
    logger.info(f"📱 [MOCK] SMS → {telefono}: {body}")


def send_sms(telefono: str, body: str):
    if SMS_PROVIDER == "twilio":
        send_sms_twilio(telefono, body)
    else:
        send_sms_mock(telefono, body)


def handle(session, message: dict):
    contrato = resolve_contrato(session, message["identificador"], message["valor"])
    if not contrato:
        raise ValueError(f"Contrato no resuelto: {message}")
    data = load_data(session, contrato, message["periodo"])
    if not data:
        raise ValueError(f"Datos no encontrados: {contrato}")
    if not data["telefono"]:
        raise ValueError("Sin teléfono registrado")
    body = (f"SEMAPA: Sr. {data['apellido']} su recibo {message['periodo']} es "
            f"Bs {data['factura']['monto_bs']}. Consumo {data['factura']['consumo_m3']} m³.")
    send_sms(data["telefono"], body)


def main():
    cluster, session = connect_cassandra()
    while True:
        try:
            creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=creds,
                heartbeat=60, blocked_connection_timeout=30,
            )
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE, durable=True, arguments={
                "x-dead-letter-exchange": "semapa.notifications.dlx",
            })
            channel.basic_qos(prefetch_count=8)

            def cb(ch, method, properties, body):
                retries = (properties.headers or {}).get("x-retries", 0) if properties else 0
                try:
                    handle(session, json.loads(body))
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Fallo ({retries}/{MAX_RETRIES}): {e}")
                    if retries < MAX_RETRIES:
                        new_props = pika.BasicProperties(
                            content_type="application/json", delivery_mode=2,
                            headers={"x-retries": retries + 1})
                        time.sleep(2 ** retries)
                        ch.basic_publish("semapa.notifications", "notify.sms", body, new_props)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    else:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(QUEUE, on_message_callback=cb)
            logger.info(f"Worker SMS consumiendo {QUEUE}")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logger.warning(f"AMQP desconectado: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            break

    cluster.shutdown()


if __name__ == "__main__":
    main()
