"""Canal MÓVIL (supernumerario). NUNCA expone `cantidad_erp`.

- GET  /movil/mi-listado  → el listado activo asignado + audio_url por ítem.
- POST /movil/conteos      → registra un conteo con trazabilidad.
Recuento libre: mientras la toma esté abierta se aceptan nuevos conteos del mismo
ítem; vale el `intento_num` mayor (el último).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.models import (
    Bodega,
    Conteo,
    EstadoAudio,
    EstadoListado,
    EstadoToma,
    Item,
    ListadoConteo,
    ListadoItem,
    RolUsuario,
    TomaInventario,
    Usuario,
)
from app.schemas import MovilConteoCreate, MovilConteoRead, MovilItem, MovilListado
from app.util import frase_confirmacion, unidad_texto

router = APIRouter(prefix="/movil", tags=["movil"])
solo_supernumerario = require_roles(RolUsuario.supernumerario)


def _listado_vigente(db: Session, user: Usuario) -> ListadoConteo:
    """Listado vigente del supernumerario: activo Y de una toma ABIERTA.

    La toma tiene que estar abierta. Sin esa condición, un listado de una toma ya
    cerrada seguía apareciendo en el móvil y el supernumerario contaba contra un
    listado muerto hasta chocar con el 409 de `registrar_conteo`.
    """
    listado = db.scalar(
        select(ListadoConteo)
        .join(TomaInventario, TomaInventario.id == ListadoConteo.toma_id)
        .where(
            ListadoConteo.supernumerario_id == user.id,
            ListadoConteo.estado == EstadoListado.activo,
            TomaInventario.estado == EstadoToma.abierta,
        )
        .order_by(ListadoConteo.id.desc())
    )
    if not listado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tiene un listado activo asignado")
    return listado


@router.get("/mi-listado", response_model=MovilListado, summary="Listado asignado (sin cantidades del ERP)")
def mi_listado(db: Session = Depends(get_db), user: Usuario = Depends(solo_supernumerario)) -> MovilListado:
    listado = _listado_vigente(db, user)
    bodega = db.get(Bodega, listado.bodega_id)

    filas = db.execute(
        select(ListadoItem, Item)
        .join(Item, Item.id == ListadoItem.item_id)
        .where(ListadoItem.listado_id == listado.id)
        .order_by(Item.descripcion)
    ).all()

    items: list[MovilItem] = []
    for li, item in filas:
        asset = item.audio_asset
        audio_url = (
            f"/audio/{asset.ruta_mp3}"
            if asset and asset.estado == EstadoAudio.listo and asset.ruta_mp3
            else None
        )
        items.append(
            MovilItem(
                listado_item_id=li.id,
                item_id=item.id,
                codigo_barras=item.codigo_barras,
                descripcion=item.descripcion,
                unidad=item.unidad,
                unidad_texto=unidad_texto(item.unidad),
                frase_confirmacion=frase_confirmacion(item.descripcion, item.unidad),
                audio_url=audio_url,
                contado=li.contado,
            )
        )

    return MovilListado(
        listado_id=listado.id,
        toma_id=listado.toma_id,
        bodega_id=listado.bodega_id,
        bodega_nombre=bodega.nombre if bodega else "",
        items=items,
    )


@router.post("/conteos", response_model=MovilConteoRead, status_code=status.HTTP_201_CREATED)
def registrar_conteo(
    data: MovilConteoCreate, db: Session = Depends(get_db), user: Usuario = Depends(solo_supernumerario)
) -> MovilConteoRead:
    # El ítem se resuelve por sí mismo, NO a través del listado vigente: un
    # conteo capturado offline puede llegar cuando la toma ya se cerró o el
    # listado se reasignó, y el móvil necesita distinguir "reintenta" de
    # "nunca se va a aceptar". Todo lo definitivo responde 409, que la cola
    # local (`resolverSync`) marca como conflicto; un 404 lo reintentaría
    # para siempre.
    li = db.get(ListadoItem, data.listado_item_id)
    if not li:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El ítem no existe")

    listado = db.get(ListadoConteo, li.listado_id)
    if not listado or listado.supernumerario_id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este listado ya no está asignado a usted")
    if listado.estado != EstadoListado.activo:
        raise HTTPException(status.HTTP_409_CONFLICT, "El listado ya no está activo; no se aceptan conteos")

    toma = db.get(TomaInventario, listado.toma_id)
    if not toma or toma.estado != EstadoToma.abierta:
        raise HTTPException(status.HTTP_409_CONFLICT, "La toma está cerrada; no se aceptan conteos")

    ultimo = db.scalar(
        select(func.max(Conteo.intento_num)).where(Conteo.listado_item_id == li.id)
    ) or 0

    conteo = Conteo(
        listado_item_id=li.id,
        cantidad_contada=data.cantidad_contada,
        contado_por=user.id,
        metodo=data.metodo,
        entrada=data.entrada,
        intento_num=ultimo + 1,
    )
    db.add(conteo)
    li.contado = True
    db.commit()
    db.refresh(conteo)

    return MovilConteoRead(
        id=conteo.id,
        listado_item_id=conteo.listado_item_id,
        cantidad_contada=conteo.cantidad_contada,
        contado_en=conteo.contado_en,
        intento_num=conteo.intento_num,
    )
