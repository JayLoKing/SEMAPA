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
import uuid
from datetime import date, datetime
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from cassandra.util import uuid_from_time
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


# Data real no incluye teléfono → destinatario de prueba (Twilio trial verificado)
NOTIFY_TEST_PHONE = os.getenv("NOTIFY_TEST_PHONE", "")


def resolve_contrato(session, identificador, valor):
    """Devuelve (numero_contrato CT-xxx, titular)."""
    if identificador == "contrato":
        nc = valor.strip().upper()
        rows = list(session.execute("SELECT titular_contrato FROM contratos WHERE numero_contrato = %s", (nc,)))
        return (nc, rows[0]["titular_contrato"] if rows else "Cliente")
    if identificador == "mac":
        rows = list(session.execute(
            "SELECT numero_contrato, titular_contrato FROM contrato_por_mac WHERE medidor_iot = %s",
            (valor.upper(),)))
        if rows:
            return (rows[0]["numero_contrato"], rows[0].get("titular_contrato") or "Cliente")
    if identificador == "carnet":
        for ci in {valor, f"{valor} CBBA", valor.split()[0] if valor.split() else valor}:
            rows = list(session.execute(
                "SELECT numero_contrato FROM contratos_por_ci WHERE ci_titular = %s", (ci,)))
            if rows:
                nc = rows[0]["numero_contrato"]
                t = list(session.execute("SELECT titular_contrato FROM contratos WHERE numero_contrato = %s", (nc,)))
                return (nc, t[0]["titular_contrato"] if t else "Cliente")
    return (None, None)


def load_data(session, contrato, titular, periodo):
    """Factura del periodo; si no existe la calcula desde lecturas."""
    factura = list(session.execute(
        "SELECT monto_bs, consumo_m3 FROM facturas WHERE numero_contrato = %s AND periodo = %s",
        (contrato, periodo)))
    if factura:
        f = factura[0]
        return {"telefono": NOTIFY_TEST_PHONE, "apellido": titular or "Cliente",
                "factura": {"monto_bs": f["monto_bs"], "consumo_m3": f["consumo_m3"]}}
    # Fallback: consumo desde lecturas (sin monto facturado)
    crow = list(session.execute("SELECT medidor_iot FROM contratos WHERE numero_contrato = %s", (contrato,)))
    if not crow or not crow[0].get("medidor_iot"):
        return None
    mac = crow[0]["medidor_iot"].upper()
    lect = list(session.execute(
        "SELECT consumo_m3 FROM lecturas_por_medidor WHERE mac = %s AND periodo = %s", (mac, periodo)))
    consumo = sum(int(l.get("consumo_m3") or 0) for l in lect)
    return {"telefono": NOTIFY_TEST_PHONE, "apellido": titular or "Cliente",
            "factura": {"monto_bs": "s/factura", "consumo_m3": consumo}}


def _normalize_phone_e164(tel: str) -> str:
    """Convierte teléfono boliviano a E.164 (+591XXXXXXXX)."""
    tel = tel.strip().replace(" ", "").replace("-", "")
    if tel.startswith("+"):
        return tel
    if len(tel) == 8 and tel.isdigit():
        return f"+591{tel}"
    return f"+{tel}" if tel.isdigit() else tel


def log_preaviso(session, contrato, periodo, canal, estado, destino, prov_id="", error=""):
    """Registra cada envío en preavisos_log para dashboard de efectividad."""
    try:
        now = datetime.utcnow()
        session.execute(
            "INSERT INTO preavisos_log (fecha, enviado_en, preaviso_id, numero_contrato, "
            "periodo, canal, estado, destino, proveedor_id, error) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (date.today(), now, uuid_from_time(now), contrato or "?", periodo or "?",
             canal, estado, destino or "", prov_id, error[:200])
        )
    except Exception as e:
        logger.warning(f"log_preaviso fallo: {e}")


def send_sms_twilio(telefono: str, body: str) -> str:
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
    return msg.sid


def send_sms_mock(telefono: str, body: str) -> str:
    logger.info(f"📱 [MOCK] SMS → {telefono}: {body}")
    return f"mock-{uuid.uuid4().hex[:12]}"


def send_sms(telefono: str, body: str) -> str:
    if SMS_PROVIDER == "twilio":
        return send_sms_twilio(telefono, body)
    return send_sms_mock(telefono, body)


def handle(session, message: dict):
    contrato, titular = resolve_contrato(session, message["identificador"], message["valor"])
    periodo = message.get("periodo", "?")
    if not contrato:
        log_preaviso(session, None, periodo, "sms", "FALLO", "", error="contrato no resuelto")
        raise ValueError(f"Contrato no resuelto: {message}")
    data = load_data(session, contrato, titular, periodo)
    if not data:
        log_preaviso(session, contrato, periodo, "sms", "FALLO", "", error="sin datos")
        raise ValueError(f"Datos no encontrados: {contrato}")
    if not data["telefono"]:
        log_preaviso(session, contrato, periodo, "sms", "FALLO", "", error="sin telefono")
        raise ValueError("Sin teléfono destino (configura NOTIFY_TEST_PHONE)")
    body = (f"SEMAPA: Sr(a). {data['apellido']} su preaviso {periodo} es "
            f"Bs {data['factura']['monto_bs']}. Consumo {data['factura']['consumo_m3']} m³.")
    try:
        sid = send_sms(data["telefono"], body)
        log_preaviso(session, contrato, periodo, "sms", "ENVIADO", data["telefono"], sid)
    except Exception as e:
        log_preaviso(session, contrato, periodo, "sms", "FALLO", data["telefono"], error=str(e))
        raise


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
