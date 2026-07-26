"""Tomas de inventario (ciclo abrir/cerrar/aceptar). Admin y supervisor.

Regla: a lo sumo UNA toma abierta por bodega.

El ciclo termina en la comparación ERP vs. conteo, donde el supervisor decide:
**aceptar** el inventario (sello con quién y cuándo, la toma sigue cerrada) o
**solicitar reconteo** (reabre la toma y revive sus listados para que el
supernumerario vuelva a contar). Son las dos únicas salidas de una toma cerrada,
y son excluyentes: pedir reconteo borra la aceptación previa."""
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
from app.routers.listados import _otra_asignacion_vigente
from app.schemas import TomaCreate, TomaRead

router = APIRouter(prefix="/tomas", tags=["tomas"])
web_roles = require_roles(RolUsuario.administrador, RolUsuario.supervisor)


def _to_read(db: Session, toma: TomaInventario) -> TomaRead:
    """`aceptada_por_nombre` no es una columna: se resuelve aquí para que la web
    pueda mostrar «Aceptado por X» sin pedir el usuario por separado."""
    nombre = None
    if toma.aceptada_por is not None:
        usuario = db.get(Usuario, toma.aceptada_por)
        nombre = usuario.nombre if usuario else None
    return TomaRead(
        id=toma.id,
        bodega_id=toma.bodega_id,
        estado=toma.estado,
        fecha_apertura=toma.fecha_apertura,
        fecha_cierre=toma.fecha_cierre,
        aceptada_en=toma.aceptada_en,
        aceptada_por=toma.aceptada_por,
        aceptada_por_nombre=nombre,
    )


@router.post("", response_model=TomaRead, status_code=status.HTTP_201_CREATED)
def abrir_toma(data: TomaCreate, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)) -> TomaRead:
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
    return _to_read(db, toma)


@router.post("/{toma_id}/cerrar", response_model=TomaRead)
def cerrar_toma(toma_id: int, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)) -> TomaRead:
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
    # (sin poder contar, la toma ya no acepta conteos) y seguirían bloqueando
    # sus ítems frente a cualquier asignación futura.
    for listado in db.scalars(
        select(ListadoConteo).where(
            ListadoConteo.toma_id == toma.id,
            ListadoConteo.estado == EstadoListado.activo,
        )
    ).all():
        listado.estado = EstadoListado.completado

    db.commit()
    db.refresh(toma)
    return _to_read(db, toma)


def _preparar_reapertura(db: Session, toma_id: int, user: Usuario) -> TomaInventario:
    """Validaciones comunes a `reabrir` y `solicitar-reconteo`: la toma existe, es
    accesible, está cerrada y su bodega no tiene ya otra toma abierta."""
    toma = db.get(TomaInventario, toma_id)
    if not toma:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Toma no encontrada")
    _verificar_acceso(db, user, toma.bodega_id)
    if toma.estado == EstadoToma.abierta:
        raise HTTPException(status.HTTP_409_CONFLICT, "La toma ya está abierta")

    otra_abierta = db.scalar(
        select(TomaInventario).where(
            TomaInventario.bodega_id == toma.bodega_id,
            TomaInventario.estado == EstadoToma.abierta,
        )
    )
    if otra_abierta:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ya hay una toma abierta (#{otra_abierta.id}) para esta bodega",
        )
    return toma


@router.post("/{toma_id}/reabrir", response_model=TomaRead)
def reabrir_toma(toma_id: int, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)) -> TomaRead:
    """Revierte el cierre de una toma cerrada por error, antes de terminar los conteos.

    No revive los listados que quedaron `completado` al cerrarla (ver `cerrar_toma`):
    el supervisor los reactiva a mano con `PATCH /listados/{id}`. Para revivirlos
    todos de una vez está `solicitar-reconteo`, que es la acción de negocio.
    """
    toma = _preparar_reapertura(db, toma_id, user)
    toma.estado = EstadoToma.abierta
    toma.fecha_cierre = None
    # Reabrir invalida la aceptación: lo aprobado fue un conteo que va a cambiar.
    toma.aceptada_en = None
    toma.aceptada_por = None
    db.commit()
    db.refresh(toma)
    return _to_read(db, toma)


@router.post("/{toma_id}/aceptar", response_model=TomaRead)
def aceptar_toma(toma_id: int, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)) -> TomaRead:
    """Sella el inventario como aceptado tras revisar la comparación ERP vs. conteo.

    Exige la toma **cerrada**: aceptar un conteo que todavía admite conteos nuevos
    sellaría una foto que puede cambiar un segundo después. No bloquea por ítems
    pendientes ni por diferencias críticas —aceptar con faltantes conocidos es una
    decisión legítima del supervisor—, pero la web se los muestra antes de confirmar.
    """
    toma = db.get(TomaInventario, toma_id)
    if not toma:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Toma no encontrada")
    _verificar_acceso(db, user, toma.bodega_id)
    if toma.estado != EstadoToma.cerrada:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Solo se puede aceptar una toma cerrada. Ciérrela primero para congelar el conteo.",
        )
    if toma.aceptada_en is not None:
        quien = db.get(Usuario, toma.aceptada_por) if toma.aceptada_por else None
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Esta toma ya fue aceptada por {quien.nombre if quien else 'otro usuario'}.",
        )

    toma.aceptada_en = datetime.now(timezone.utc)
    toma.aceptada_por = user.id
    db.commit()
    db.refresh(toma)
    return _to_read(db, toma)


@router.post("/{toma_id}/solicitar-reconteo", response_model=TomaRead)
def solicitar_reconteo(toma_id: int, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)) -> TomaRead:
    """Devuelve la toma a campo: la reabre y revive sus listados `completado`.

    Es la otra salida de la comparación. A diferencia de `reabrir` —que solo
    corrige un cierre por error— aquí el objetivo es que el supernumerario vuelva
    a contar, y para eso el listado tiene que volver a estar `activo`: el móvil
    solo entrega listados activos de tomas abiertas.

    No hace falta revalidar el solape de ítems entre los listados que revive:
    `crear_listado` exige la toma abierta, así que mientras estuvo cerrada nadie
    pudo añadir listados, y los que se cierran juntos ya tenían ítems disjuntos.
    Sí se revalida la invariante «un supernumerario, un listado vigente», porque
    alguien pudo recibir otra asignación en otra bodega mientras tanto. Si alguno
    choca no se revive nada: media reapertura es peor que ninguna.
    """
    toma = _preparar_reapertura(db, toma_id, user)

    a_revivir = list(db.scalars(
        select(ListadoConteo).where(
            ListadoConteo.toma_id == toma.id,
            ListadoConteo.estado == EstadoListado.completado,
        )
    ).all())

    choques = []
    for listado in a_revivir:
        if listado.supernumerario_id is None:
            continue
        vigente = _otra_asignacion_vigente(db, listado.supernumerario_id, excluir_listado_id=listado.id)
        if vigente:
            sup = db.get(Usuario, listado.supernumerario_id)
            bodega = db.get(Bodega, vigente.bodega_id)
            choques.append(
                f"{sup.nombre if sup else 'un supernumerario'} ya tiene el listado #{vigente.id} "
                f"activo en {bodega.nombre if bodega else 'otra bodega'}"
            )
    if choques:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se puede pedir reconteo: " + "; ".join(choques)
            + ". Cancele o termine esa asignación y vuelva a intentarlo.",
        )

    toma.estado = EstadoToma.abierta
    toma.fecha_cierre = None
    toma.aceptada_en = None
    toma.aceptada_por = None
    for listado in a_revivir:
        listado.estado = EstadoListado.activo

    db.commit()
    db.refresh(toma)
    return _to_read(db, toma)


@router.get("", response_model=list[TomaRead])
def listar_tomas(
    bodega_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> list[TomaRead]:
    stmt = select(TomaInventario).order_by(TomaInventario.fecha_apertura.desc())
    if bodega_id is not None:
        stmt = stmt.where(TomaInventario.bodega_id == bodega_id)
    if user.rol == RolUsuario.supervisor:
        stmt = stmt.where(TomaInventario.bodega_id.in_({b.id for b in user.bodegas}))
    return [_to_read(db, t) for t in db.scalars(stmt).all()]


@router.delete("/{toma_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_toma(toma_id: int, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)) -> None:
    """Deshace una toma abierta por error (bodega equivocada, prueba, duplicado).

    Sin restricción por estado ni por conteos ya registrados: el ON DELETE CASCADE
    de la FK (toma → listado_conteo → listado_item → conteo, ver migración inicial)
    se encarga de borrar todo lo asociado. Irreversible; la web lo advierte antes
    de confirmar.
    """
    toma = db.get(TomaInventario, toma_id)
    if not toma:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Toma no encontrada")
    _verificar_acceso(db, user, toma.bodega_id)
    db.delete(toma)
    db.commit()
