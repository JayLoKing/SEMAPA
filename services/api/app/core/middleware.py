"""Middlewares: logs JSON, rate-limit Redis."""
from __future__ import annotations

import time

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis_client import redis_client


class JsonLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.time()
        response = await call_next(request)
        elapsed_ms = (time.time() - t0) * 1000
        logger.info(
            "{method} {path} → {status} {elapsed_ms:.1f}ms",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_min: int = 100):
        super().__init__(app)
        self.limit = limit_per_min

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        key = f"rl:{ip}"
        try:
            n = await redis_client.incr(key, ttl_seconds=60)
        except Exception:
            # Redis no disponible → no bloqueamos
            return await call_next(request)
        if n > self.limit:
            return JSONResponse({"detail": "rate_limit_exceeded"}, status_code=429)
        return await call_next(request)
