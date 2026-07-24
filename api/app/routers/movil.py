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


def _listado_activo(db: Session, user: Usuario) -> ListadoConteo:
    listado = db.scalar(
        select(ListadoConteo)
        .where(
            ListadoConteo.supernumerario_id == user.id,
            ListadoConteo.estado == EstadoListado.activo,
        )
        .order_by(ListadoConteo.id.desc())
    )
    if not listado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tiene un listado activo asignado")
    return listado


@router.get("/mi-listado", response_model=MovilListado, summary="Listado asignado (sin cantidades del ERP)")
def mi_listado(db: Session = Depends(get_db), user: Usuario = Depends(solo_supernumerario)) -> MovilListado:
    listado = _listado_activo(db, user)
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
    listado = _listado_activo(db, user)

    li = db.get(ListadoItem, data.listado_item_id)
    if not li or li.listado_id != listado.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El ítem no pertenece a su listado")

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
