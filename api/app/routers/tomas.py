"""Tomas de inventario (ciclo abrir/cerrar). Admin y supervisor.

Regla: a lo sumo UNA toma abierta por bodega (refuerza el bloqueo de concurrencia:
si solo hay una toma abierta por bodega, solo puede haber un listado activo)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.models import (
    Bodega,
    EstadoListado,
    EstadoToma,
    ListadoConteo,
    RolUsuario,
    TomaInventario,
    Usuario,
)
from app.routers.bodegas import _verificar_acceso
from app.schemas import TomaCreate, TomaRead

router = APIRouter(prefix="/tomas", tags=["tomas"])
web_roles = require_roles(RolUsuario.administrador, RolUsuario.supervisor)


@router.post("", response_model=TomaRead, status_code=status.HTTP_201_CREATED)
def abrir_toma(data: TomaCreate, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)) -> TomaInventario:
    if not db.get(Bodega, data.bodega_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bodega no encontrada")
    _verificar_acceso(db, user, data.bodega_id)
    abierta = db.scalar(
        select(TomaInventario).where(
            TomaInventario.bodega_id == data.bodega_id,
            TomaInventario.estado == EstadoToma.abierta,
        )
    )
    if abierta:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay una toma abierta para esta bodega")
    toma = TomaInventario(bodega_id=data.bodega_id, creada_por=user.id)
    db.add(toma)
    db.commit()
    db.refresh(toma)
    return toma


@router.post("/{toma_id}/cerrar", response_model=TomaRead)
def cerrar_toma(toma_id: int, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)) -> TomaInventario:
    toma = db.get(TomaInventario, toma_id)
    if not toma:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Toma no encontrada")
    _verificar_acceso(db, user, toma.bodega_id)
    if toma.estado == EstadoToma.cerrada:
        raise HTTPException(status.HTTP_409_CONFLICT, "La toma ya está cerrada")
    toma.estado = EstadoToma.cerrada
    toma.fecha_cierre = datetime.now(timezone.utc)

    # Cerrar la toma cierra sus asignaciones. Si no, los listados quedan
    # `activo` para siempre: el supernumerario los seguiría viendo en el móvil
    # (sin poder contar, la toma ya no acepta conteos) y el índice único de
    # concurrencia seguiría contándolos como asignación vigente.
    for listado in db.scalars(
        select(ListadoConteo).where(
            ListadoConteo.toma_id == toma.id,
            ListadoConteo.estado == EstadoListado.activo,
        )
    ).all():
        listado.estado = EstadoListado.completado

    db.commit()
    db.refresh(toma)
    return toma


@router.get("", response_model=list[TomaRead])
def listar_tomas(
    bodega_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> list[TomaInventario]:
    stmt = select(TomaInventario).order_by(TomaInventario.fecha_apertura.desc())
    if bodega_id is not None:
        stmt = stmt.where(TomaInventario.bodega_id == bodega_id)
    if user.rol == RolUsuario.supervisor:
        stmt = stmt.where(TomaInventario.bodega_id.in_({b.id for b in user.bodegas}))
    return list(db.scalars(stmt).all())
