"""Listados de conteo (asignación a supernumerarios). Admin y supervisor.

BLOQUEO DE CONCURRENCIA: el índice único parcial `uq_listado_activo_toma_bodega`
impide que exista más de un listado ACTIVO por (toma, bodega). Si dos peticiones
compiten, la segunda recibe 409. El audio se genera en segundo plano (on-demand).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.models import (
    Bodega,
    EstadoListado,
    EstadoToma,
    Item,
    ListadoConteo,
    ListadoItem,
    RolUsuario,
    TomaInventario,
    Usuario,
)
from app.routers.bodegas import _verificar_acceso
from app.schemas import ListadoCreate, ListadoRead
from app.services.tts import ensure_audio_for_listado

router = APIRouter(prefix="/listados", tags=["listados"])
web_roles = require_roles(RolUsuario.administrador, RolUsuario.supervisor)


def _to_read(db: Session, listado: ListadoConteo) -> ListadoRead:
    total = db.scalar(
        select(func.count()).select_from(ListadoItem).where(ListadoItem.listado_id == listado.id)
    )
    contados = db.scalar(
        select(func.count()).select_from(ListadoItem).where(
            ListadoItem.listado_id == listado.id, ListadoItem.contado.is_(True)
        )
    )
    return ListadoRead(
        id=listado.id,
        toma_id=listado.toma_id,
        bodega_id=listado.bodega_id,
        supernumerario_id=listado.supernumerario_id,
        estado=listado.estado,
        total_items=total or 0,
        contados=contados or 0,
    )


@router.post("", response_model=ListadoRead, status_code=status.HTTP_201_CREATED)
def crear_listado(
    data: ListadoCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> ListadoRead:
    _verificar_acceso(db, user, data.bodega_id)

    toma = db.get(TomaInventario, data.toma_id)
    if not toma or toma.bodega_id != data.bodega_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Toma no encontrada para esa bodega")
    if toma.estado != EstadoToma.abierta:
        raise HTTPException(status.HTTP_409_CONFLICT, "La toma no está abierta")

    sup = db.get(Usuario, data.supernumerario_id)
    if not sup or sup.rol != RolUsuario.supernumerario:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El usuario asignado no es supernumerario")
    if data.bodega_id not in {b.id for b in sup.bodegas}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "El supernumerario no está asignado a esa bodega")

    listado = ListadoConteo(
        toma_id=data.toma_id,
        bodega_id=data.bodega_id,
        supernumerario_id=data.supernumerario_id,
        estado=EstadoListado.activo,
        creado_por=user.id,
    )
    db.add(listado)
    try:
        db.flush()  # dispara el índice único parcial
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya existe un listado activo para esta bodega en esta toma (asignado a otro supernumerario)",
        )

    # Ítems del listado: los indicados, o todos los de la bodega.
    if data.item_ids:
        item_ids = set(db.scalars(
            select(Item.id).where(Item.id.in_(data.item_ids), Item.bodega_id == data.bodega_id)
        ).all())
    else:
        item_ids = set(db.scalars(select(Item.id).where(Item.bodega_id == data.bodega_id)).all())
    if not item_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La bodega no tiene ítems para asignar")

    db.add_all([ListadoItem(listado_id=listado.id, item_id=iid) for iid in item_ids])
    db.commit()
    db.refresh(listado)

    # Pre-generación de audio on-demand (dedup + caché), fuera del request.
    background.add_task(ensure_audio_for_listado, listado.id)
    return _to_read(db, listado)


@router.get("", response_model=list[ListadoRead])
def listar_listados(
    toma_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> list[ListadoRead]:
    stmt = select(ListadoConteo).order_by(ListadoConteo.id.desc())
    if toma_id is not None:
        stmt = stmt.where(ListadoConteo.toma_id == toma_id)
    if user.rol == RolUsuario.supervisor:
        stmt = stmt.where(ListadoConteo.bodega_id.in_({b.id for b in user.bodegas}))
    return [_to_read(db, lst) for lst in db.scalars(stmt).all()]


@router.get("/{listado_id}", response_model=ListadoRead)
def obtener_listado(listado_id: int, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)) -> ListadoRead:
    listado = db.get(ListadoConteo, listado_id)
    if not listado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listado no encontrado")
    _verificar_acceso(db, user, listado.bodega_id)
    return _to_read(db, listado)
