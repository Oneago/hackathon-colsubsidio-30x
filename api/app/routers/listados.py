"""Listados de conteo (asignación a supernumerarios). Admin y supervisor.

BLOQUEO DE CONCURRENCIA: pueden coexistir varios listados ACTIVOS para la
misma (toma, bodega), uno por supernumerario, siempre que sus ítems no se
solapen. Un `pg_advisory_xact_lock(toma_id)` (`_bloquear_toma`) serializa el
chequeo de solape + insert dentro de la transacción, evitando la carrera en
vez de detectarla después; `_conflicto_solape` hace el chequeo en Python para
poder devolver un mensaje que diga QUÉ ítems están en conflicto y con QUIÉN —
un 409 anónimo deja al supervisor sin salida.

REASIGNACIÓN: `PATCH /listados/{id}` es la única forma de cambiar de
supernumerario o de cancelar. Sin él, un error al asignar obligaba a cerrar la
toma entera.

El audio se genera en segundo plano (on-demand).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select, text
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
from app.routers.bodegas import _items_tomados_ids, _verificar_acceso
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


_LOCK_NS_LISTADOS = 875_501  # namespace arbitrario para pg_advisory_xact_lock(ns, toma_id)


def _bloquear_toma(db: Session, toma_id: int) -> None:
    """Serializa el chequeo de solape + insert por toma dentro de la
    transacción actual (se libera solo al hacer commit/rollback). Reemplaza al
    antiguo índice único parcial como defensa de concurrencia: en vez de
    detectar la carrera después (IntegrityError), la evita poniendo en fila a
    las peticiones concurrentes de la misma toma."""
    db.execute(text("SELECT pg_advisory_xact_lock(:ns, :toma_id)"), {"ns": _LOCK_NS_LISTADOS, "toma_id": toma_id})


def _conflicto_solape(
    db: Session, toma_id: int, item_ids: set[int], excluir_listado_id: int | None = None
) -> tuple[ListadoConteo, int] | None:
    """Si algún ítem de `item_ids` ya pertenece a OTRO listado activo de esta
    toma, devuelve (ese listado, cuántos ítems se solapan con él) — el listado
    con más ítems en conflicto, si hay varios. Es la validación que reemplaza
    a la antigua "un solo listado activo por bodega": ahora la exclusividad es
    por ítem, no por bodega entera."""
    if not item_ids:
        return None
    stmt = (
        select(ListadoConteo, func.count(ListadoItem.item_id))
        .join(ListadoItem, ListadoItem.listado_id == ListadoConteo.id)
        .where(
            ListadoConteo.toma_id == toma_id,
            ListadoConteo.estado == EstadoListado.activo,
            ListadoItem.item_id.in_(item_ids),
        )
        .group_by(ListadoConteo.id)
        .order_by(func.count(ListadoItem.item_id).desc())
    )
    if excluir_listado_id is not None:
        stmt = stmt.where(ListadoConteo.id != excluir_listado_id)
    fila = db.execute(stmt).first()
    return (fila[0], fila[1]) if fila else None


def _nombre_dueno(db: Session, listado: ListadoConteo) -> str:
    dueno = db.get(Usuario, listado.supernumerario_id) if listado.supernumerario_id else None
    return dueno.nombre if dueno else "otro supernumerario"


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

    # Serializa el resto de esta función por toma: dos peticiones concurrentes
    # para la misma toma ya no pueden calcular "ítems disponibles" sobre la
    # misma foto y crear el mismo ítem en dos listados.
    _bloquear_toma(db, data.toma_id)

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
        if not item_ids:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La bodega no tiene ítems para asignar")
        # Selección explícita: si solapa con otro listado activo, se rechaza
        # entera (el supervisor decide qué quitar), no se recorta en silencio.
        conflicto = _conflicto_solape(db, data.toma_id, item_ids)
        if conflicto:
            otro, n = conflicto
            quien = _nombre_dueno(db, otro)
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{n} de los ítems seleccionados ya están en el listado #{otro.id} de {quien} "
                "(activo en esta toma). Quítelos de la selección, o cancele/edite ese listado, "
                "para continuar.",
            )
    else:
        todos = set(db.scalars(select(Item.id).where(Item.bodega_id == data.bodega_id)).all())
        if not todos:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La bodega no tiene ítems para asignar")
        # Sin selección explícita: por defecto se asignan los ítems
        # DISPONIBLES (no tomados por otro listado activo de esta toma), no
        # todos los de la bodega.
        item_ids = todos - _items_tomados_ids(db, data.toma_id)
        if not item_ids:
            # `todos` quedó cubierto por completo por listados activos de esta
            # toma: _conflicto_solape siempre encuentra al menos uno.
            conflicto = _conflicto_solape(db, data.toma_id, todos)
            otro = conflicto[0] if conflicto else None
            quien = _nombre_dueno(db, otro) if otro else "otro supernumerario"
            detalle_listado = f" (listado #{otro.id})" if otro else ""
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Esta bodega ya está completamente asignada a {quien} en esta toma"
                f"{detalle_listado}. Reasigne o cancele ese listado, o indique ítems "
                "puntuales, para asignar el resto.",
            )

    listado = ListadoConteo(
        toma_id=data.toma_id,
        bodega_id=data.bodega_id,
        supernumerario_id=data.supernumerario_id,
        estado=EstadoListado.activo,
        creado_por=user.id,
    )
    db.add(listado)
    db.flush()

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
        # Reactivar exige que ninguno de sus ítems esté ya en otro listado
        # activo de esta toma (la exclusividad es por ítem, no por bodega).
        if data.estado == EstadoListado.activo:
            _bloquear_toma(db, listado.toma_id)
            item_ids = set(
                db.scalars(select(ListadoItem.item_id).where(ListadoItem.listado_id == listado.id)).all()
            )
            conflicto = _conflicto_solape(db, listado.toma_id, item_ids, excluir_listado_id=listado.id)
            if conflicto:
                otro, n = conflicto
                quien = _nombre_dueno(db, otro)
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"No se puede reactivar: {n} de sus ítems ya están en el listado #{otro.id} de "
                    f"{quien} (activo en esta toma). Cancele o edite ese listado primero.",
                )
        listado.estado = data.estado

    db.commit()
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

    Tampoco permite agregar ítems que ya estén en OTRO listado activo de esta
    misma toma: la exclusividad de ítems entre listados activos es lo que
    reemplaza a la antigua exclusividad por bodega.
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

    _bloquear_toma(db, listado.toma_id)

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

    conflicto = _conflicto_solape(db, listado.toma_id, nuevos, excluir_listado_id=listado.id)
    if conflicto:
        otro, n = conflicto
        quien = _nombre_dueno(db, otro)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se pueden agregar: {n} de los ítems seleccionados ya están en el listado #{otro.id} "
            f"de {quien} (activo en esta toma). Quítelos de la selección, o cancele/edite ese listado.",
        )

    db.add_all([ListadoItem(listado_id=listado.id, item_id=iid) for iid in nuevos])
    db.commit()

    background.add_task(ensure_audio_for_listado, listado.id)
    return _to_read(db, listado)
