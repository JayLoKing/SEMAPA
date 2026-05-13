"""SEMAPA — Worker WhatsApp (Twilio Sandbox).

Consume `notify.whatsapp` desde RabbitMQ y envía vía Twilio WhatsApp Sandbox.

Variables de entorno:
  WHATSAPP_PROVIDER             twilio | mock  (default twilio)
  TWILIO_ACCOUNT_SID            AC...
  TWILIO_AUTH_TOKEN
  TWILIO_WHATSAPP_FROM          whatsapp:+14155238886  (sandbox)
  TWILIO_WHATSAPP_TEMPLATE_SID  HXxxxx (template para 24h+; opcional)

Sandbox Twilio:
  El destinatario debe haber enviado primero "join glass-fifty" al
  +1 415 523 8886. Si está dentro de ventana 24h se envía como `body=`;
  fuera de ventana solo templates pre-aprobados (`content_sid`).
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

QUEUE = "notify.whatsapp"
MAX_RETRIES = 3

WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "twilio").lower()
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WA_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
TWILIO_WA_TEMPLATE = os.getenv("TWILIO_WHATSAPP_TEMPLATE_SID", "")

_twilio: TwilioClient | None = None
if WHATSAPP_PROVIDER == "twilio" and TWILIO_SID and TWILIO_TOKEN:
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


def resolve(session, identificador, valor):
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
    f = list(session.execute(
        "SELECT monto_bs, consumo_m3 FROM facturas WHERE numero_contrato = %s AND periodo = %s",
        (contrato, periodo)))
    if not f:
        return None
    m = list(session.execute("SELECT infraestructura_id FROM medidores WHERE numero_contrato = %s", (contrato,)))
    tel = None
    apellido = "Cliente"
    if m:
        inf = list(session.execute("SELECT persona_id FROM infraestructuras WHERE infraestructura_id = %s",
                                   (m[0]["infraestructura_id"],)))
        if inf:
            p = list(session.execute(
                "SELECT telefono, apellidos, razon_social, tipo FROM personas WHERE persona_id = %s",
                (inf[0]["persona_id"],)))
            if p:
                tel = p[0].get("telefono")
                apellido = p[0].get("razon_social") if p[0].get("tipo") == "JURIDICA" else p[0].get("apellidos")
    return {"f": f[0], "tel": tel, "apellido": apellido}


def _normalize_phone_e164(tel: str) -> str:
    tel = tel.strip().replace(" ", "").replace("-", "")
    if tel.startswith("+"):
        return tel
    if len(tel) == 8 and tel.isdigit():
        return f"+591{tel}"
    return f"+{tel}" if tel.isdigit() else tel


def send_whatsapp_twilio(tel: str, body: str, content_vars: dict | None = None):
    if _twilio is None:
        raise RuntimeError("Twilio no configurado")
    to = f"whatsapp:{_normalize_phone_e164(tel)}"
    kwargs: dict = {"from_": TWILIO_WA_FROM, "to": to}
    # Si hay template, usar content_sid (mandatorio fuera de ventana 24h).
    if TWILIO_WA_TEMPLATE and content_vars is not None:
        kwargs["content_sid"] = TWILIO_WA_TEMPLATE
        kwargs["content_variables"] = json.dumps(content_vars)
    else:
        kwargs["body"] = body
    msg = _twilio.messages.create(**kwargs)
    logger.info(f"💬 WhatsApp Twilio sid={msg.sid} → {to}")


def send_whatsapp_mock(tel: str, body: str):
    logger.info(f"💬 [MOCK] WhatsApp → {tel}: {body}")


def send_whatsapp(tel: str, body: str, content_vars: dict | None = None):
    if WHATSAPP_PROVIDER == "twilio":
        send_whatsapp_twilio(tel, body, content_vars)
    else:
        send_whatsapp_mock(tel, body)


def handle(session, msg: dict):
    contrato = resolve(session, msg["identificador"], msg["valor"])
    if not contrato:
        raise ValueError(f"Contrato no resuelto: {msg}")
    data = load_data(session, contrato, msg["periodo"])
    if not data or not data["tel"]:
        raise ValueError("Sin teléfono o factura")
    body = (f"SEMAPA — Hola Sr. {data['apellido']}. Recibo {msg['periodo']}: "
            f"Bs {data['f']['monto_bs']}. Consumo {data['f']['consumo_m3']} m³. "
            f"Gracias por su pago puntual.")
    # Variables del template demo Twilio (HXb5b... = "Your appointment is on {{1}} at {{2}}")
    content_vars = {"1": msg["periodo"], "2": f"Bs {data['f']['monto_bs']}"}
    send_whatsapp(data["tel"], body, content_vars=content_vars)


def main():
    cluster, session = connect_cassandra()
    while True:
        try:
            creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=creds,
                heartbeat=60, blocked_connection_timeout=30)
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
                        ch.basic_publish("semapa.notifications", "notify.whatsapp", body, new_props)
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    else:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(QUEUE, on_message_callback=cb)
            logger.info(f"Worker WhatsApp consumiendo {QUEUE}")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logger.warning(f"AMQP desconectado: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            break

    cluster.shutdown()


if __name__ == "__main__":
    main()
