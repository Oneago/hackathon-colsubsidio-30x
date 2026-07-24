"""Bodegas e inventario (canal WEB). El admin ve todas; el supervisor solo las suyas.
El inventario web SÍ incluye `cantidad_erp` (comparación posterior)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.models import Bodega, Item, RolUsuario, Usuario
from app.schemas import BodegaRead, ItemRead

router = APIRouter(prefix="/bodegas", tags=["bodegas"])
web_roles = require_roles(RolUsuario.administrador, RolUsuario.supervisor)


def bodega_ids_accesibles(db: Session, user: Usuario) -> set[int] | None:
    """None = todas (admin). Set = ids permitidos (supervisor)."""
    if user.rol == RolUsuario.administrador:
        return None
    return {b.id for b in user.bodegas}


def _verificar_acceso(db: Session, user: Usuario, bodega_id: int) -> None:
    permitidas = bodega_ids_accesibles(db, user)
    if permitidas is not None and bodega_id not in permitidas:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene acceso a esta bodega")


@router.get("", response_model=list[BodegaRead])
def listar_bodegas(
    solo_operativas: bool = False,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> list[Bodega]:
    stmt = select(Bodega).order_by(Bodega.nombre)
    permitidas = bodega_ids_accesibles(db, user)
    if permitidas is not None:
        stmt = stmt.where(Bodega.id.in_(permitidas))
    if solo_operativas:
        stmt = stmt.where(Bodega.es_operativa.is_(True))
    return list(db.scalars(stmt).all())


@router.get("/{bodega_id}/items", response_model=list[ItemRead])
def items_de_bodega(
    bodega_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> list[Item]:
    _verificar_acceso(db, user, bodega_id)
    return list(
        db.scalars(select(Item).where(Item.bodega_id == bodega_id).order_by(Item.descripcion)).all()
    )
