"""SEMAPA — Worker email.

Consume `notify.email` desde RabbitMQ. Por cada mensaje:
  1. Resuelve persona+factura desde Cassandra (por contrato/carnet/mac).
  2. Pide los 2 PDFs (rollo + medicarta) al pdf-service.
  3. Envía via Mailtrap Sending API (o SMTP a Mailhog en dev) con los 2 PDFs.

Reintentos exponenciales (3) y luego DLQ vía x-dead-letter-exchange.

Variables de entorno:
  EMAIL_PROVIDER          mailtrap | mailhog (default mailtrap)
  MAILTRAP_TOKEN          Token de API Mailtrap
  MAILTRAP_INBOX_ID       (vacío para sending real; con id usa Testing API)
  SMTP_FROM               Email del remitente
  SMTP_FROM_NAME          Nombre del remitente
  SMTP_HOST/PORT          Para mailhog fallback
"""
from __future__ import annotations

import base64
import json
import os
import smtplib
import time
import uuid
from datetime import date, datetime
from email.message import EmailMessage

import httpx
import pika
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from cassandra.util import uuid_from_time
from loguru import logger


# --------------------- config ---------------------
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "semapa")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "semapa")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "mailtrap").lower()
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@demomailtrap.co")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "SEMAPA")

MAILTRAP_TOKEN = os.getenv("MAILTRAP_TOKEN", "")
MAILTRAP_INBOX_ID = os.getenv("MAILTRAP_INBOX_ID", "")  # vacío = sending real

SMTP_HOST = os.getenv("SMTP_HOST", "mailhog")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))

PDF_BASE = os.getenv("PDF_BASE_URL", "http://pdf-service:8001")

CASSANDRA_HOSTS = os.getenv("CASSANDRA_HOSTS", "cassandra-1,cassandra-2").split(",")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "semapa")
CASSANDRA_USER = os.getenv("CASSANDRA_USER", "")
CASSANDRA_PASSWORD = os.getenv("CASSANDRA_PASSWORD", "")

QUEUE = "notify.email"
MAX_RETRIES = 3


# --------------------- Cassandra ---------------------
def connect_cassandra():
    auth = PlainTextAuthProvider(CASSANDRA_USER, CASSANDRA_PASSWORD) if CASSANDRA_USER else None
    for i in range(30):
        try:
            cluster = Cluster(CASSANDRA_HOSTS, port=CASSANDRA_PORT, auth_provider=auth, protocol_version=5)
            session = cluster.connect(CASSANDRA_KEYSPACE)
            session.row_factory = dict_factory
            return cluster, session
        except Exception as e:
            logger.warning(f"Cassandra retry {i+1}/30: {e}")
            time.sleep(5)
    raise RuntimeError("Cassandra no disponible")


# Data real no incluye email → destinatario de prueba (Mailtrap)
NOTIFY_TEST_EMAIL = os.getenv("NOTIFY_TEST_EMAIL", "")


# --------------------- lookups ---------------------
def resolve_contrato(session, identificador: str, valor: str):
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


def load_factura(session, numero_contrato: str, periodo: str) -> dict | None:
    rows = list(session.execute(
        "SELECT * FROM facturas WHERE numero_contrato = %s AND periodo = %s",
        (numero_contrato, periodo),
    ))
    return rows[0] if rows else None


# --------------------- PDFs ---------------------
def fetch_pdf(numero_contrato: int, periodo: str, formato: str) -> bytes:
    r = httpx.get(
        f"{PDF_BASE}/pdf",
        params={"numero_contrato": numero_contrato, "periodo": periodo, "formato": formato},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.content


# --------------------- Senders ---------------------
def send_mailhog(to: str, subject: str, body: str, attachments: list[tuple[str, bytes]]):
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    for fname, content in attachments:
        msg.add_attachment(content, maintype="application", subtype="pdf", filename=fname)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
        s.send_message(msg)


def send_mailtrap(to: str, subject: str, body: str, attachments: list[tuple[str, bytes]]):
    """Mailtrap Sending API (POST https://send.api.mailtrap.io/api/send)."""
    if not MAILTRAP_TOKEN:
        raise RuntimeError("MAILTRAP_TOKEN no configurado")

    base = "https://sandbox.api.mailtrap.io" if MAILTRAP_INBOX_ID else "https://send.api.mailtrap.io"
    path = f"/api/send/{MAILTRAP_INBOX_ID}" if MAILTRAP_INBOX_ID else "/api/send"

    payload = {
        "from": {"email": SMTP_FROM, "name": SMTP_FROM_NAME},
        "to": [{"email": to}],
        "subject": subject,
        "text": body,
        "category": "SEMAPA Factura",
        "attachments": [
            {
                "filename": fname,
                "type": "application/pdf",
                "disposition": "attachment",
                "content": base64.b64encode(content).decode("ascii"),
            }
            for fname, content in attachments
        ],
    }
    r = httpx.post(
        f"{base}{path}",
        json=payload,
        headers={
            "Authorization": f"Bearer {MAILTRAP_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=15.0,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Mailtrap fallo {r.status_code}: {r.text[:300]}")


def send_email(to: str, subject: str, body: str, attachments: list[tuple[str, bytes]]):
    if EMAIL_PROVIDER == "mailtrap":
        send_mailtrap(to, subject, body, attachments)
    else:
        send_mailhog(to, subject, body, attachments)


# --------------------- Tracking ---------------------
def log_preaviso(session, contrato, periodo, canal, estado, destino, prov_id="", error=""):
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


# --------------------- Handler ---------------------
def handle(session, message: dict):
    contrato, apellido = resolve_contrato(session, message["identificador"], message["valor"])
    periodo = message.get("periodo", "?")
    if not contrato:
        log_preaviso(session, None, periodo, "email", "FALLO", "", error="contrato no resuelto")
        raise ValueError(f"Contrato no resuelto: {message}")
    factura = load_factura(session, contrato, periodo)
    if not factura:
        log_preaviso(session, contrato, periodo, "email", "FALLO", "", error="factura no existe")
        raise ValueError(f"Factura no encontrada: {contrato} {periodo} (genera con /facturas/generar)")
    email = NOTIFY_TEST_EMAIL
    if not email:
        log_preaviso(session, contrato, periodo, "email", "FALLO", "", error="sin email destino")
        raise ValueError("Sin email destino (configura NOTIFY_TEST_EMAIL)")

    body = (
        f"Sr(a). {apellido}, SEMAPA le recuerda que su recibo de consumo de agua es de "
        f"Bs {factura['monto_bs']}. Por el período {periodo} usted consumió "
        f"{factura['consumo_m3']} m³ de agua."
    )
    subject = f"SEMAPA — Factura {periodo} (Contrato {contrato})"

    pdfs = [
        (f"factura-{contrato}-{periodo}-medicarta.pdf",
         fetch_pdf(contrato, periodo, "medicarta")),
        (f"factura-{contrato}-{periodo}-rollo.pdf",
         fetch_pdf(contrato, periodo, "rollo")),
    ]
    try:
        send_email(email, subject, body, pdfs)
        logger.info(f"Email ({EMAIL_PROVIDER}) → {email} ({contrato}/{periodo})")
        log_preaviso(session, contrato, periodo, "email", "ENVIADO", email,
                     f"{EMAIL_PROVIDER}-{uuid.uuid4().hex[:8]}")
    except Exception as e:
        log_preaviso(session, contrato, periodo, "email", "FALLO", email, error=str(e))
        raise


# --------------------- Main loop ---------------------
def main():
    cluster, session = connect_cassandra()
    logger.info(f"Worker email iniciado (provider={EMAIL_PROVIDER})")

    while True:
        try:
            creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST, port=RABBITMQ_PORT,
                virtual_host=RABBITMQ_VHOST, credentials=creds,
                heartbeat=60, blocked_connection_timeout=30,
            )
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE, durable=True, arguments={
                "x-dead-letter-exchange": "semapa.notifications.dlx",
            })
            channel.basic_qos(prefetch_count=4)

            def callback(ch, method, properties, body):
                retries = (properties.headers or {}).get("x-retries", 0) if properties else 0
                try:
                    msg = json.loads(body)
                    handle(session, msg)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Fallo procesando ({retries}/{MAX_RETRIES}): {e}")
                    if retries < MAX_RETRIES:
                        new_props = pika.BasicProperties(
                            content_type="application/json",
                            delivery_mode=2,
                            headers={"x-retries": retries + 1},
                        )
                        time.sleep(2 ** retries)
                        ch.basic_publish(
                            exchange="semapa.notifications",
                            routing_key="notify.email",
                            body=body,
                            properties=new_props,
                        )
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    else:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            channel.basic_consume(queue=QUEUE, on_message_callback=callback)
            logger.info(f"Worker email consumiendo {QUEUE}...")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logger.warning(f"AMQP desconectado: {e}; reintentando en 5s")
            time.sleep(5)
        except KeyboardInterrupt:
            break

    cluster.shutdown()


if __name__ == "__main__":
    main()
