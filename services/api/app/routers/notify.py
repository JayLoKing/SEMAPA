"""Notify router: publica mensajes a RabbitMQ."""
from __future__ import annotations

import json

import aio_pika
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.core.config import settings
from app.core.security import current_user
from app.models.schemas import NotifyIn


router = APIRouter()

_EXCHANGE = "semapa.notifications"


@router.post("")
async def publish(body: NotifyIn, _u: dict = Depends(current_user)):
    routing_key = f"notify.{body.formato}"
    try:
        connection = await aio_pika.connect_robust(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            login=settings.RABBITMQ_USER,
            password=settings.RABBITMQ_PASSWORD,
            virtualhost=settings.RABBITMQ_VHOST,
            timeout=5.0,
        )
    except Exception as e:
        logger.error(f"RabbitMQ no disponible: {e}")
        raise HTTPException(503, "Broker no disponible")

    async with connection:
        channel = await connection.channel()
        exch = await channel.declare_exchange(_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        await exch.publish(
            aio_pika.Message(
                body=json.dumps(body.model_dump()).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
    return {"published": True, "routing_key": routing_key}
