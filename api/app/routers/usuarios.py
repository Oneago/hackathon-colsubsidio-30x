"""Gestión de usuarios (solo administrador).

Valida en la API la regla de negocio (además del modelo):
- supernumerario → EXACTAMENTE 1 bodega
- supervisor     → 1..N bodegas
- administrador  → todas (no requiere lista; ve todo)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.models import Bodega, RolUsuario, Usuario
from app.routers.bodegas import bodega_ids_accesibles
from app.schemas import UsuarioCreate, UsuarioRead, UsuarioResetPassword, UsuarioUpdate
from app.security import hash_password

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
solo_admin = require_roles(RolUsuario.administrador)
# El supervisor no gestiona la plantilla, pero sí necesita ver a los
# supernumerarios de SUS bodegas para poder asignarles un listado.
web_roles = require_roles(RolUsuario.administrador, RolUsuario.supervisor)


def _resolver_bodegas(db: Session, rol: RolUsuario, bodega_ids: list[int]) -> list[Bodega]:
    if rol == RolUsuario.administrador:
        return []  # el admin ve todas; no se persiste lista
    if rol == RolUsuario.supernumerario and len(bodega_ids) != 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Un supernumerario debe tener exactamente 1 bodega")
    if rol == RolUsuario.supervisor and len(bodega_ids) < 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Un supervisor debe tener al menos 1 bodega")
    bodegas = db.scalars(select(Bodega).where(Bodega.id.in_(bodega_ids))).all()
    if len(bodegas) != len(set(bodega_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alguna bodega no existe")
    return list(bodegas)


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def crear_usuario(data: UsuarioCreate, db: Session = Depends(get_db), _=Depends(solo_admin)) -> Usuario:
    if db.scalar(select(Usuario).where(Usuario.cedula == data.cedula)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con esa cédula")
    bodegas = _resolver_bodegas(db, data.rol, data.bodega_ids)
    user = Usuario(
        nombre=data.nombre,
        cedula=data.cedula,
        password_hash=hash_password(data.password),
        rol=data.rol,
        must_change_password=True,
        bodegas=bodegas,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=list[UsuarioRead])
def listar_usuarios(db: Session = Depends(get_db), _=Depends(solo_admin)) -> list[Usuario]:
    return list(db.scalars(select(Usuario).order_by(Usuario.id)).all())


@router.get("/supernumerarios", response_model=list[UsuarioRead])
def listar_supernumerarios(
    bodega_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> list[Usuario]:
    """Supernumerarios asignables, acotados al alcance del solicitante.

    Existe porque `GET /usuarios` es solo-admin: sin esta ruta el supervisor no
    puede poblar el desplegable de asignación y queda sin poder asignar nada.
    Devuelve solo lo justo para asignar, nunca la plantilla completa.
    """
    stmt = (
        select(Usuario)
        .where(Usuario.rol == RolUsuario.supernumerario, Usuario.activo.is_(True))
        .order_by(Usuario.nombre)
    )
    permitidas = bodega_ids_accesibles(db, user)
    if bodega_id is not None:
        if permitidas is not None and bodega_id not in permitidas:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene acceso a esta bodega")
        permitidas = {bodega_id}
    if permitidas is not None:
        stmt = stmt.where(Usuario.bodegas.any(Bodega.id.in_(permitidas)))
    return list(db.scalars(stmt).all())


@router.get("/{usuario_id}", response_model=UsuarioRead)
def obtener_usuario(usuario_id: int, db: Session = Depends(get_db), _=Depends(solo_admin)) -> Usuario:
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return user


@router.post("/{usuario_id}/reset-password", response_model=UsuarioRead)
def restablecer_password(
    usuario_id: int,
    data: UsuarioResetPassword,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(solo_admin),
) -> Usuario:
    """Asigna una contraseña nueva a otro usuario (olvido de clave en campo)."""
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if user.id == admin.id:
        # La clave propia se cambia por /auth/change-password, que sí exige la
        # actual: así una sesión abierta no permite apoderarse de la cuenta.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Para cambiar su propia contraseña use el cambio de contraseña, no el restablecimiento",
        )
    user.password_hash = hash_password(data.password_nueva)
    user.must_change_password = False  # la clave que asigna el admin es la definitiva
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{usuario_id}", response_model=UsuarioRead)
def actualizar_usuario(
    usuario_id: int, data: UsuarioUpdate, db: Session = Depends(get_db), _=Depends(solo_admin)
) -> Usuario:
    user = db.get(Usuario, usuario_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if data.nombre is not None:
        user.nombre = data.nombre
    if data.activo is not None:
        user.activo = data.activo
    if data.bodega_ids is not None:
        user.bodegas = _resolver_bodegas(db, user.rol, data.bodega_ids)
    db.commit()
    db.refresh(user)
    return user
