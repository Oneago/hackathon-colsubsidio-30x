"""Autenticación: login por canal (web / móvil), cambio de contraseña y /me.

Regla: el supernumerario NO entra por web (rechazo explícito); el supervisor NO
entra por la app móvil. El admin puede por ambos canales.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import RolUsuario, Usuario
from app.schemas import ChangePasswordRequest, LoginRequest, MeResponse, TokenResponse
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate(db: Session, cedula: str, password: str) -> Usuario:
    user = db.scalar(select(Usuario).where(Usuario.cedula == cedula))
    if user is None or not user.activo or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cédula o contraseña incorrecta",
        )
    return user


def _token_for(user: Usuario) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(sub=user.id, rol=user.rol.value),
        rol=user.rol,
        nombre=user.nombre,
        must_change_password=user.must_change_password,
    )


@router.post("/login/web", response_model=TokenResponse, summary="Login de la consola web")
def login_web(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = _authenticate(db, data.cedula, data.password)
    if user.rol == RolUsuario.supernumerario:
        # Rechazo EXPLÍCITO (no un error genérico).
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Los supernumerarios solo acceden por la aplicación móvil, no por la web.",
        )
    return _token_for(user)


@router.post("/login/movil", response_model=TokenResponse, summary="Login de la app móvil (cédula + contraseña)")
def login_movil(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = _authenticate(db, data.cedula, data.password)
    if user.rol == RolUsuario.supervisor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El supervisor gestiona desde la web, no desde la app móvil.",
        )
    return _token_for(user)


@router.post("/change-password", summary="Cambio de contraseña (primer ingreso o rotación)")
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> dict:
    if not verify_password(data.password_actual, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no coincide")
    user.password_hash = hash_password(data.password_nueva)
    user.must_change_password = False
    db.commit()
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse, summary="Datos del usuario autenticado")
def me(user: Usuario = Depends(get_current_user)) -> Usuario:
    return user
