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
from email.message import EmailMessage

import httpx
import pika
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
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


# --------------------- lookups ---------------------
def resolve_contrato(session, identificador: str, valor: str) -> int | None:
    if identificador == "contrato":
        return int(valor)
    if identificador == "mac":
        rows = list(session.execute("SELECT numero_contrato FROM medidores WHERE mac = %s", (valor.upper(),)))
        return rows[0]["numero_contrato"] if rows else None
    if identificador == "carnet":
        rows = list(session.execute("SELECT persona_id FROM personas WHERE documento = %s", (valor,)))
        if not rows:
            return None
        infras = list(session.execute(
            "SELECT infraestructura_id FROM infraestructuras WHERE persona_id = %s",
            (rows[0]["persona_id"],),
        ))
        for inf in infras:
            meds = list(session.execute(
                "SELECT numero_contrato FROM medidores WHERE infraestructura_id = %s ALLOW FILTERING",
                (inf["infraestructura_id"],),
            ))
            if meds:
                return meds[0]["numero_contrato"]
    return None


def load_factura(session, numero_contrato: int, periodo: str) -> dict | None:
    rows = list(session.execute(
        "SELECT * FROM facturas WHERE numero_contrato = %s AND periodo = %s",
        (numero_contrato, periodo),
    ))
    return rows[0] if rows else None


def load_persona_email(session, numero_contrato: int) -> tuple[str | None, str | None]:
    meds = list(session.execute(
        "SELECT infraestructura_id FROM medidores WHERE numero_contrato = %s",
        (numero_contrato,),
    ))
    if not meds:
        return None, None
    infs = list(session.execute(
        "SELECT persona_id FROM infraestructuras WHERE infraestructura_id = %s",
        (meds[0]["infraestructura_id"],),
    ))
    if not infs:
        return None, None
    pers = list(session.execute(
        "SELECT email, apellidos, razon_social, tipo FROM personas WHERE persona_id = %s",
        (infs[0]["persona_id"],),
    ))
    if not pers:
        return None, None
    p = pers[0]
    apellido = p.get("razon_social") if p.get("tipo") == "JURIDICA" else p.get("apellidos")
    return p.get("email"), apellido or "Cliente"


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


# --------------------- Handler ---------------------
def handle(session, message: dict):
    contrato = resolve_contrato(session, message["identificador"], message["valor"])
    if not contrato:
        raise ValueError(f"Contrato no resuelto: {message}")
    periodo = message["periodo"]
    factura = load_factura(session, contrato, periodo)
    if not factura:
        raise ValueError(f"Factura no encontrada: {contrato} {periodo}")
    email, apellido = load_persona_email(session, contrato)
    if not email:
        raise ValueError(f"Email no encontrado para contrato {contrato}")

    body = (
        f"Sr. {apellido}, SEMAPA le recuerda que su recibo de consumo de agua es de "
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
    send_email(email, subject, body, pdfs)
    logger.info(f"Email ({EMAIL_PROVIDER}) → {email} ({contrato}/{periodo})")


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
