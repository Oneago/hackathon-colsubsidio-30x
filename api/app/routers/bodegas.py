"""Bodegas e inventario (canal WEB). El admin ve todas; el supervisor solo las suyas.
El inventario web SÍ incluye `cantidad_erp` (comparación posterior)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.models import Bodega, EstadoListado, Item, ListadoConteo, ListadoItem, RolUsuario, Usuario
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


def _items_tomados_ids(db: Session, toma_id: int, excluir_listado_id: int | None = None) -> set[int]:
    """Ids de ítems ya cubiertos por listados ACTIVOS de esta toma (de cualquier
    supernumerario). Único criterio de "disponible" para el selector de la web
    (`GET /bodegas/{id}/items?toma_id=`) y para las validaciones de solape en
    `routers/listados.py`."""
    stmt = (
        select(ListadoItem.item_id)
        .join(ListadoConteo, ListadoConteo.id == ListadoItem.listado_id)
        .where(ListadoConteo.toma_id == toma_id, ListadoConteo.estado == EstadoListado.activo)
    )
    if excluir_listado_id is not None:
        stmt = stmt.where(ListadoConteo.id != excluir_listado_id)
    return set(db.scalars(stmt).all())


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
    toma_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> list[Item]:
    """Si se pasa `toma_id`, excluye los ítems ya cubiertos por un listado
    ACTIVO de esa toma (de cualquier supernumerario) — así el selector de
    asignación nunca ofrece ítems que ya están en manos de otro."""
    _verificar_acceso(db, user, bodega_id)
    stmt = select(Item).where(Item.bodega_id == bodega_id)
    if toma_id is not None:
        tomados = _items_tomados_ids(db, toma_id)
        if tomados:
            stmt = stmt.where(Item.id.notin_(tomados))
    return list(db.scalars(stmt.order_by(Item.descripcion)).all())
