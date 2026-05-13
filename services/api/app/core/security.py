"""Security utilities: JWT, bcrypt, role-based guards."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger

from app.core.config import settings


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# === Roles ===
ROLE_ALCALDIA = "ALCALDIA"
ROLE_GERENCIA = "GERENCIA"
ROLE_CONTABILIDAD = "CONTABILIDAD"
ALL_ROLES = (ROLE_ALCALDIA, ROLE_GERENCIA, ROLE_CONTABILIDAD)


# === Password helpers ===
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# === JWT ===
def create_access_token(username: str, rol: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "rol": rol,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_EXPIRES_MIN)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")


# === Dependency: current user ===
def current_user(token: str | None = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta token")
    return decode_token(token)


# === Role guard factory ===
def require_roles(roles: Sequence[str]):
    """Devuelve una dependency que valida el rol del JWT."""
    role_set = set(roles)

    def _guard(user: dict = Depends(current_user)) -> dict:
        if user.get("rol") not in role_set:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol no autorizado")
        return user

    return _guard
