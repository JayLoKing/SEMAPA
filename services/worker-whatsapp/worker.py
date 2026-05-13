"""SEMAPA — Worker WhatsApp (mock).

Consume `notify.whatsapp` desde RabbitMQ. Sin Meta Cloud API real; loguea.
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


def send_whatsapp_mock(tel: str, body: str):
    logger.info(f"💬 WhatsApp → {tel}: {body}")


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
    send_whatsapp_mock(data["tel"], body)


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
