"""Seed idempotente: carga `inventory.json` (respuesta simulada del ERP) en la base.

Idempotencia: hace upsert por claves naturales, de modo que correrlo N veces
deja exactamente el mismo estado (no duplica).

Transformaciones:
- Crea las 48 bodegas del listado (por `id_erp`).
- Aplica el mapeo manual stock→bodega (bodega_stock_map.json) y marca operativas.
- Normaliza la unidad de medida (inglés → enum es-CO).
- Genera `codigo_barras` para los ítems sin `nrArticulo` (18% del dataset).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Bodega, Item, RolUsuario, UnidadMedida, Usuario
from app.security import hash_password
from app.seed.usuarios_demo import ensure_usuarios_demo

MAP_PATH = Path(__file__).parent / "bodega_stock_map.json"

# Unidad ERP (inglés) → enum canónico es-CO.
UOM_MAP = {
    "unidad": UnidadMedida.unidad,
    "kilogram": UnidadMedida.kilogramo,
    "liter": UnidadMedida.litro,
    "portion": UnidadMedida.porcion,
}


def strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def normalize_desc(text: str) -> str:
    """Clave natural estable para deduplicar/upsert: sin acentos, mayúsculas, sin espacios extra."""
    return re.sub(r"\s+", " ", strip_accents(text)).strip().upper()


def clean_display(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().title()


def map_uom(raw: str | None) -> UnidadMedida:
    return UOM_MAP.get((raw or "").strip().lower(), UnidadMedida.unidad)


def gen_codigo_barras(descripcion_norm: str) -> str:
    """Código sintético estable para ítems sin nrArticulo. Prefijo 'GEN-' para no
    colisionar nunca con los códigos numéricos reales del ERP."""
    h = hashlib.sha1(descripcion_norm.encode("utf-8")).hexdigest()[:10].upper()
    return f"GEN-{h}"


def upsert_bodega(
    db: Session, *, id_erp: int | None, nombre: str, slug: str | None, es_operativa: bool
) -> Bodega:
    bodega: Bodega | None = None
    if id_erp is not None:
        bodega = db.scalar(select(Bodega).where(Bodega.id_erp == id_erp))
    if bodega is None and slug is not None:
        bodega = db.scalar(select(Bodega).where(Bodega.slug == slug))

    if bodega is None:
        bodega = Bodega(id_erp=id_erp, nombre=nombre, slug=slug, es_operativa=es_operativa)
        db.add(bodega)
        db.flush()
    else:
        bodega.nombre = nombre
        if slug is not None:
            bodega.slug = slug
        # Una bodega marcada operativa nunca se "desmarca" al recargar.
        bodega.es_operativa = bodega.es_operativa or es_operativa
    return bodega


def upsert_item(db: Session, *, bodega_id: int, existing: dict[str, Item], raw: dict) -> bool:
    """Devuelve True si insertó (nuevo), False si actualizó."""
    descripcion = re.sub(r"\s+", " ", str(raw["articulo"])).strip()
    desc_norm = normalize_desc(descripcion)
    nr = raw.get("nrArticulo")
    codigo = str(nr) if nr is not None else gen_codigo_barras(desc_norm)
    unidad = map_uom(raw.get("unidad"))
    cantidad = raw.get("stock") or 0

    item = existing.get(desc_norm)
    if item is None:
        db.add(
            Item(
                bodega_id=bodega_id,
                nr_articulo=nr,
                codigo_barras=codigo,
                descripcion=descripcion,
                descripcion_norm=desc_norm,
                unidad=unidad,
                cantidad_erp=cantidad,
            )
        )
        return True

    item.nr_articulo = nr
    item.codigo_barras = codigo
    item.descripcion = descripcion
    item.unidad = unidad
    item.cantidad_erp = cantidad
    return False


def ensure_admin(db: Session, settings) -> bool:
    """Crea el usuario administrador inicial si no existe. Devuelve True si lo creó."""
    if db.scalar(select(Usuario).where(Usuario.cedula == settings.admin_cedula)):
        return False
    db.add(
        Usuario(
            nombre=settings.admin_nombre,
            cedula=settings.admin_cedula,
            password_hash=hash_password(settings.admin_password),
            rol=RolUsuario.administrador,
            must_change_password=True,
        )
    )
    return True


def run() -> None:
    settings = get_settings()
    dataset = json.loads(Path(settings.dataset_path).read_text(encoding="utf-8"))
    mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))["map"]

    inserted = updated = 0
    with SessionLocal() as db:
        admin_creado = ensure_admin(db, settings)
        # 1) Las 48 bodegas del listado (catálogo de referencia).
        for b in dataset["bodegas"]:
            upsert_bodega(
                db,
                id_erp=int(b["id"]),
                nombre=clean_display(b["nombre"]),
                slug=None,
                es_operativa=False,
            )
        db.flush()

        # 2) Stock → bodega (mapeo manual) + ítems.
        for slug, obj in dataset["stock"].items():
            conf = mapping.get(slug, {"bodega_id_erp": None, "nombre": None})
            id_erp = conf.get("bodega_id_erp")
            if id_erp is not None:
                bodega = upsert_bodega(
                    db, id_erp=int(id_erp), nombre=clean_display(obj["nombre"]),
                    slug=None, es_operativa=True,
                )
            else:
                nombre = conf.get("nombre") or clean_display(obj["nombre"])
                bodega = upsert_bodega(
                    db, id_erp=None, nombre=nombre, slug=slug, es_operativa=True,
                )
            db.flush()

            existing = {
                it.descripcion_norm: it
                for it in db.scalars(select(Item).where(Item.bodega_id == bodega.id)).all()
            }
            for raw in obj["items"]:
                if upsert_item(db, bodega_id=bodega.id, existing=existing, raw=raw):
                    inserted += 1
                else:
                    updated += 1

        # 3) Plantilla demo. Va al final a propósito: necesita las bodegas ya creadas
        # para resolverlas por clave natural.
        demo_creados = demo_actualizados = 0
        if settings.seed_usuarios_demo:
            demo_creados, demo_actualizados = ensure_usuarios_demo(db, settings.demo_password)

        db.commit()

        n_bodegas = len(db.scalars(select(Bodega.id)).all())
        n_operativas = len(db.scalars(select(Bodega.id).where(Bodega.es_operativa.is_(True))).all())
        n_items = len(db.scalars(select(Item.id)).all())

    print(
        f"[seed] OK · admin={'creado' if admin_creado else 'existente'} · "
        f"usuarios demo: creados={demo_creados}, actualizados={demo_actualizados} · "
        f"bodegas={n_bodegas} (operativas={n_operativas}) · "
        f"items insertados={inserted}, actualizados={updated}, total={n_items}"
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(f"[seed] ERROR: {exc}", file=sys.stderr)
        raise
