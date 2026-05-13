"""Auth router: login, /me, logout."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.cassandra_client import cassandra_client
from app.core.security import (create_access_token, current_user,
                               verify_password)
from app.models.schemas import LoginIn, LoginOut, UserMe


router = APIRouter()


@router.post("/login", response_model=LoginOut)
async def login(body: LoginIn):
    rows = list(cassandra_client.execute("auth_get_user", (body.username,)))
    if not rows:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
    user = rows[0]
    if not user.get("activo"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario inactivo")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")

    cassandra_client.execute("auth_touch_user", (datetime.utcnow(), body.username))
    token = create_access_token(user["username"], user["rol"])
    return LoginOut(
        access_token=token,
        rol=user["rol"],
        nombre=user.get("nombre") or user["username"],
        email=user.get("email"),
    )


@router.get("/me", response_model=UserMe)
async def me(user: dict = Depends(current_user)):
    return UserMe(username=user["sub"], rol=user["rol"])


@router.post("/logout")
async def logout(user: dict = Depends(current_user)):
    # JWT stateless: el cliente descarta el token. (Opcional: blacklist en Redis.)
    return {"detail": "logout_ok"}
