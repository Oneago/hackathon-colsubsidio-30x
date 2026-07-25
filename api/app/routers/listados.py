"""Listados de conteo (asignación a supernumerarios). Admin y supervisor.

BLOQUEO DE CONCURRENCIA: el índice único parcial `uq_listado_activo_toma_bodega`
impide que exista más de un listado ACTIVO por (toma, bodega). Ese índice es la
última línea de defensa (carrera entre dos peticiones); antes de llegar a él se
comprueba en Python para poder devolver un mensaje que diga QUIÉN tiene la
asignación y cómo liberarla — un 409 anónimo deja al supervisor sin salida.

REASIGNACIÓN: `PATCH /listados/{id}` es la única forma de cambiar de
supernumerario o de cancelar. Sin él, un error al asignar obligaba a cerrar la
toma entera.

El audio se genera en segundo plano (on-demand).
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
from app.schemas import ItemRead, ListadoCreate, ListadoItemsAdd, ListadoRead, ListadoUpdate
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
    sup = db.get(Usuario, listado.supernumerario_id) if listado.supernumerario_id else None
    bodega = db.get(Bodega, listado.bodega_id)
    return ListadoRead(
        id=listado.id,
        toma_id=listado.toma_id,
        bodega_id=listado.bodega_id,
        supernumerario_id=listado.supernumerario_id,
        supernumerario_nombre=sup.nombre if sup else None,
        bodega_nombre=bodega.nombre if bodega else "",
        estado=listado.estado,
        total_items=total or 0,
        contados=contados or 0,
    )


def _validar_supernumerario(db: Session, supernumerario_id: int, bodega_id: int) -> Usuario:
    sup = db.get(Usuario, supernumerario_id)
    if not sup or sup.rol != RolUsuario.supernumerario:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El usuario asignado no es supernumerario")
    if not sup.activo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{sup.nombre} está inactivo")
    if bodega_id not in {b.id for b in sup.bodegas}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "El supernumerario no está asignado a esa bodega")
    return sup


def _listado_activo_de(db: Session, toma_id: int, bodega_id: int) -> ListadoConteo | None:
    return db.scalar(
        select(ListadoConteo).where(
            ListadoConteo.toma_id == toma_id,
            ListadoConteo.bodega_id == bodega_id,
            ListadoConteo.estado == EstadoListado.activo,
        )
    )


def _otra_asignacion_vigente(
    db: Session, supernumerario_id: int, excluir_listado_id: int | None = None
) -> ListadoConteo | None:
    """Otro listado activo del mismo supernumerario en una toma ABIERTA.

    El móvil (`/movil/mi-listado`) entrega un único listado, así que dos
    asignaciones vigentes a la vez significan que una queda invisible en campo:
    se bloquea en vez de perderla en silencio. Solo cuentan las tomas abiertas —
    las cerradas ya no admiten conteos.
    """
    stmt = (
        select(ListadoConteo)
        .join(TomaInventario, TomaInventario.id == ListadoConteo.toma_id)
        .where(
            ListadoConteo.supernumerario_id == supernumerario_id,
            ListadoConteo.estado == EstadoListado.activo,
            TomaInventario.estado == EstadoToma.abierta,
        )
    )
    if excluir_listado_id is not None:
        stmt = stmt.where(ListadoConteo.id != excluir_listado_id)
    return db.scalar(stmt)


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

    sup = _validar_supernumerario(db, data.supernumerario_id, data.bodega_id)

    # Comprobación explícita antes del índice único: el mensaje debe decir quién
    # tiene la asignación y qué hacer, no solo que ya existe.
    existente = _listado_activo_de(db, data.toma_id, data.bodega_id)
    if existente:
        actual = db.get(Usuario, existente.supernumerario_id) if existente.supernumerario_id else None
        quien = actual.nombre if actual else "otro supernumerario"
        if existente.supernumerario_id == data.supernumerario_id:
            detalle = f"Esta bodega ya está asignada a {quien} en esta toma (listado #{existente.id})."
        else:
            detalle = (
                f"Esta bodega ya está asignada a {quien} en esta toma (listado #{existente.id}). "
                f"Reasigne ese listado o cancélelo para asignarlo a {sup.nombre}."
            )
        raise HTTPException(status.HTTP_409_CONFLICT, detalle)

    vigente = _otra_asignacion_vigente(db, data.supernumerario_id)
    if vigente:
        bodega_ocupada = db.get(Bodega, vigente.bodega_id)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{sup.nombre} ya tiene el listado #{vigente.id} activo en "
            f"{bodega_ocupada.nombre if bodega_ocupada else 'otra bodega'}. "
            "Debe terminarlo o cancelarlo antes de recibir otro.",
        )

    # Los ítems se resuelven ANTES de insertar: si la bodega está vacía no debe
    # quedar rastro de un listado a medio crear.
    if data.item_ids:
        item_ids = set(db.scalars(
            select(Item.id).where(Item.id.in_(data.item_ids), Item.bodega_id == data.bodega_id)
        ).all())
    else:
        item_ids = set(db.scalars(select(Item.id).where(Item.bodega_id == data.bodega_id)).all())
    if not item_ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La bodega no tiene ítems para asignar")

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
        # Solo se llega aquí si otra petición ganó la carrera entre la
        # comprobación de arriba y este INSERT.
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Otro usuario acaba de asignar esta bodega en esta toma. Recargue la página.",
        )

    db.add_all([ListadoItem(listado_id=listado.id, item_id=iid) for iid in item_ids])
    db.commit()
    db.refresh(listado)

    # Pre-generación de audio on-demand (dedup + caché), fuera del request.
    background.add_task(ensure_audio_for_listado, listado.id)
    return _to_read(db, listado)


@router.patch("/{listado_id}", response_model=ListadoRead)
def actualizar_listado(
    listado_id: int,
    data: ListadoUpdate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> ListadoRead:
    """Reasigna el listado a otro supernumerario y/o cambia su estado.

    Es la salida al 409 de `POST /listados`: permite corregir una asignación
    equivocada sin cerrar la toma.
    """
    listado = db.get(ListadoConteo, listado_id)
    if not listado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listado no encontrado")
    _verificar_acceso(db, user, listado.bodega_id)

    toma = db.get(TomaInventario, listado.toma_id)
    if not toma or toma.estado != EstadoToma.abierta:
        raise HTTPException(status.HTTP_409_CONFLICT, "La toma está cerrada; el listado ya no se puede modificar")

    nuevo_estado = data.estado if data.estado is not None else listado.estado

    if data.supernumerario_id is not None and data.supernumerario_id != listado.supernumerario_id:
        if nuevo_estado != EstadoListado.activo:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "No se puede reasignar un listado que se está cancelando o completando",
            )
        sup = _validar_supernumerario(db, data.supernumerario_id, listado.bodega_id)
        vigente = _otra_asignacion_vigente(db, data.supernumerario_id, excluir_listado_id=listado.id)
        if vigente:
            bodega_ocupada = db.get(Bodega, vigente.bodega_id)
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{sup.nombre} ya tiene el listado #{vigente.id} activo en "
                f"{bodega_ocupada.nombre if bodega_ocupada else 'otra bodega'}. "
                "Debe terminarlo o cancelarlo antes de recibir otro.",
            )
        listado.supernumerario_id = data.supernumerario_id

    if data.estado is not None and data.estado != listado.estado:
        # Reactivar exige que la bodega esté libre en esta toma (el índice único
        # lo impone; aquí se explica por qué).
        if data.estado == EstadoListado.activo:
            ocupado = _listado_activo_de(db, listado.toma_id, listado.bodega_id)
            if ocupado and ocupado.id != listado.id:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"No se puede reactivar: el listado #{ocupado.id} ya está activo en esta bodega.",
                )
        listado.estado = data.estado

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Otro usuario modificó la asignación de esta bodega. Recargue la página.",
        )
    db.refresh(listado)

    # Reasignar no cambia los ítems, pero sí puede ser la primera vez que el
    # listado queda utilizable: asegurar el audio es idempotente y barato.
    if listado.estado == EstadoListado.activo:
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


@router.get("/{listado_id}/items", response_model=list[ItemRead])
def items_del_listado(
    listado_id: int, db: Session = Depends(get_db), user: Usuario = Depends(web_roles)
) -> list[Item]:
    """Ítems ya incluidos en el listado; la web la usa para no ofrecerlos de nuevo
    al agregar ítems nuevos."""
    listado = db.get(ListadoConteo, listado_id)
    if not listado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listado no encontrado")
    _verificar_acceso(db, user, listado.bodega_id)
    return list(
        db.scalars(
            select(Item)
            .join(ListadoItem, ListadoItem.item_id == Item.id)
            .where(ListadoItem.listado_id == listado_id)
            .order_by(Item.descripcion)
        ).all()
    )


@router.patch("/{listado_id}/items", response_model=ListadoRead)
def agregar_items_listado(
    listado_id: int,
    data: ListadoItemsAdd,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> ListadoRead:
    """Agrega ítems a un listado activo (ej. el supervisor olvidó incluirlos).

    Solo agrega: no permite quitar ítems ya incluidos. Quitar un ítem borraría
    su fila `ListadoItem`, y un conteo offline en cola para ese ítem recibiría
    un 404 al sincronizar en vez del 409 que exige la invariante de la cola
    móvil (`resolverSync` reintenta los 404 para siempre). Para quitar ítems se
    sigue usando cancelar el listado y reasignar.
    """
    listado = db.get(ListadoConteo, listado_id)
    if not listado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listado no encontrado")
    _verificar_acceso(db, user, listado.bodega_id)

    toma = db.get(TomaInventario, listado.toma_id)
    if not toma or toma.estado != EstadoToma.abierta:
        raise HTTPException(status.HTTP_409_CONFLICT, "La toma está cerrada; el listado ya no se puede modificar")
    if listado.estado != EstadoListado.activo:
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se pueden agregar ítems a un listado activo")

    existentes = set(
        db.scalars(select(ListadoItem.item_id).where(ListadoItem.listado_id == listado_id)).all()
    )
    candidatos = set(
        db.scalars(
            select(Item.id).where(Item.id.in_(data.item_ids), Item.bodega_id == listado.bodega_id)
        ).all()
    )
    nuevos = candidatos - existentes
    if not nuevos:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No hay ítems nuevos para agregar")

    db.add_all([ListadoItem(listado_id=listado.id, item_id=iid) for iid in nuevos])
    db.commit()

    background.add_task(ensure_audio_for_listado, listado.id)
    return _to_read(db, listado)
