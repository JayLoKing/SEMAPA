"""Cliente Redis singleton (async)."""
from __future__ import annotations

import redis.asyncio as aioredis
from loguru import logger

from app.core.config import settings


class RedisClient:
    def __init__(self) -> None:
        self.client: aioredis.Redis | None = None

    async def connect(self) -> None:
        if self.client is not None:
            return
        self.client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
            socket_keepalive=True,
            health_check_interval=30,
        )
        await self.client.ping()
        logger.info(f"Redis conectado en {settings.REDIS_HOST}:{settings.REDIS_PORT}")

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None

    async def get(self, key: str) -> str | None:
        assert self.client is not None
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        assert self.client is not None
        if ttl_seconds:
            await self.client.set(key, value, ex=ttl_seconds)
        else:
            await self.client.set(key, value)

    async def setnx(self, key: str, value: str, ttl_seconds: int) -> bool:
        assert self.client is not None
        return bool(await self.client.set(key, value, ex=ttl_seconds, nx=True))

    async def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        assert self.client is not None
        n = await self.client.incr(key)
        if n == 1 and ttl_seconds:
            await self.client.expire(key, ttl_seconds)
        return n


redis_client = RedisClient()
