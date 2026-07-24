"""Reportes de comparación ERP vs. conteo (canal WEB). Admin y supervisor.

Toma la última cuenta (mayor `intento_num`) por ítem del listado y la compara con
la cantidad del ERP: diferencia absoluta, porcentual y marca de "crítico" según el
umbral configurable (`DIFF_UMBRAL_PCT`)."""
import csv
import io
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import require_roles
from app.models import (
    Bodega,
    Conteo,
    Item,
    ListadoConteo,
    ListadoItem,
    RolUsuario,
    TomaInventario,
    Usuario,
)
from app.routers.bodegas import _verificar_acceso
from app.schemas import ComparacionFila, ComparacionResponse, ComparacionResumen

router = APIRouter(prefix="/reportes", tags=["reportes"])
web_roles = require_roles(RolUsuario.administrador, RolUsuario.supervisor)


def _construir_comparacion(db: Session, toma_id: int, user: Usuario) -> ComparacionResponse:
    toma = db.get(TomaInventario, toma_id)
    if not toma:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Toma no encontrada")
    _verificar_acceso(db, user, toma.bodega_id)
    bodega = db.get(Bodega, toma.bodega_id)
    umbral = get_settings().diff_umbral_pct

    filas_raw = db.execute(
        select(ListadoItem, Item)
        .join(ListadoConteo, ListadoConteo.id == ListadoItem.listado_id)
        .join(Item, Item.id == ListadoItem.item_id)
        .where(ListadoConteo.toma_id == toma_id)
        .order_by(Item.descripcion)
    ).all()

    li_ids = [li.id for li, _ in filas_raw]
    ultimos: dict[int, Conteo] = {}
    if li_ids:
        for c in db.scalars(select(Conteo).where(Conteo.listado_item_id.in_(li_ids))).all():
            prev = ultimos.get(c.listado_item_id)
            if prev is None or c.intento_num > prev.intento_num:
                ultimos[c.listado_item_id] = c

    filas: list[ComparacionFila] = []
    contados = criticos = 0
    for li, item in filas_raw:
        c = ultimos.get(li.id)
        erp = Decimal(item.cantidad_erp)
        if c is None:
            filas.append(ComparacionFila(
                item_id=item.id, codigo_barras=item.codigo_barras, descripcion=item.descripcion,
                unidad=item.unidad, cantidad_erp=erp, cantidad_contada=None, contado=False,
                diff_abs=None, diff_pct=None, critico=False,
                contado_por=None, contado_en=None, metodo=None, entrada=None,
            ))
            continue

        contados += 1
        contada = Decimal(c.cantidad_contada)
        diff_abs = contada - erp
        if erp != 0:
            diff_pct = float(diff_abs) / abs(float(erp)) * 100.0
            critico = abs(diff_pct) >= umbral
        else:
            diff_pct = None
            critico = contada != 0
        if critico:
            criticos += 1

        filas.append(ComparacionFila(
            item_id=item.id, codigo_barras=item.codigo_barras, descripcion=item.descripcion,
            unidad=item.unidad, cantidad_erp=erp, cantidad_contada=contada, contado=True,
            diff_abs=diff_abs, diff_pct=diff_pct, critico=critico,
            contado_por=c.contado_por, contado_en=c.contado_en, metodo=c.metodo, entrada=c.entrada,
        ))

    total = len(filas)
    return ComparacionResponse(
        toma_id=toma.id,
        bodega_id=toma.bodega_id,
        bodega_nombre=bodega.nombre if bodega else "",
        estado=toma.estado,
        resumen=ComparacionResumen(
            total_items=total, contados=contados, pendientes=total - contados,
            criticos=criticos, umbral_pct=umbral,
        ),
        filas=filas,
    )


@router.get("/comparacion", response_model=ComparacionResponse, summary="Comparación ERP vs. conteo")
def comparacion(
    toma_id: int = Query(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> ComparacionResponse:
    return _construir_comparacion(db, toma_id, user)


@router.get("/comparacion.csv", summary="Exportar la comparación a CSV")
def comparacion_csv(
    toma_id: int = Query(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(web_roles),
) -> Response:
    data = _construir_comparacion(db, toma_id, user)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["codigo", "descripcion", "unidad", "cantidad_erp", "cantidad_contada",
         "diff_abs", "diff_pct", "critico", "estado"]
    )
    for f in data.filas:
        writer.writerow([
            f.codigo_barras, f.descripcion, f.unidad.value, f.cantidad_erp,
            f.cantidad_contada if f.cantidad_contada is not None else "",
            f.diff_abs if f.diff_abs is not None else "",
            f"{f.diff_pct:.2f}" if f.diff_pct is not None else "",
            "si" if f.critico else "no",
            "contado" if f.contado else "pendiente",
        ])
    csv_bytes = "﻿" + buffer.getvalue()  # BOM para acentos en Excel
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="comparacion_toma_{toma_id}.csv"'},
    )
