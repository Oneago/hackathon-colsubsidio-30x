"""Plantilla de demostración: supervisores y supernumerarios por bodega.

El administrador lo crea `seed.py::ensure_admin`; aquí va el **resto** de la plantilla,
la que hace demostrable el flujo completo (asignar → contar → reconciliar) sin dar de
alta usuarios a mano después de cada despliegue.

Respeta las mismas reglas que `routers/usuarios.py::_resolver_bodegas`, porque el seed
escribe el modelo directamente y se salta esa validación:

- supernumerario → EXACTAMENTE 1 bodega
- supervisor     → 1..N bodegas

Las bodegas se referencian por **clave natural** (`slug:` o `erp:`), nunca por `id`:
el id es autoincremental y no coincide entre la base local y la de producción.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bodega, RolUsuario, Usuario
from app.security import hash_password


@dataclass(frozen=True)
class UsuarioDemo:
    cedula: str
    nombre: str
    rol: RolUsuario
    bodegas: tuple[str, ...]


# Las 8 bodegas operativas del dataset, por clave natural. Las de `stock` no traen
# `id_erp` (se identifican por slug); las del catálogo del ERP sí.
_ALMACEN_AYB = "slug:stock_almacen_ayb"
_REST_FUENTES_AYB = "slug:stock_restaurante_fuentes_ayb"
_KIOSCO_TAQUILLA = "slug:stock_kiosco_taquilla_ayb"
_KIOSCO_PISCIGIROS = "slug:stock_kiosco_piscigiros_ayb"
_ALMACEN_SUMIN = "slug:stock_almacen_suministros"
_REST_FUENTES_SUMIN = "slug:stock_restaurante_fuentes_sumin"
_ZOO_SUMIN = "erp:46"
_ZOO = "erp:47"

# Cédulas por rango para que el rol se lea de un vistazo en la demo:
# 1.xxx = administrador · 2.xxx = supervisor · 3.xxx = supernumerario.
# Cada supervisor cubre bodegas donde hay supernumerarios, si no el alcance por rol
# (invariante 4) no se puede mostrar: vería listas vacías.
ROSTER: tuple[UsuarioDemo, ...] = (
    # ── Supervisores (1..N bodegas) ───────────────────────────────
    UsuarioDemo(
        "2000000001", "Sandra Milena Rojas", RolUsuario.supervisor,
        (_ALMACEN_AYB, _REST_FUENTES_AYB, _KIOSCO_TAQUILLA, _KIOSCO_PISCIGIROS),
    ),
    UsuarioDemo(
        "2000000002", "Carlos Andrés Beltrán", RolUsuario.supervisor,
        (_ALMACEN_SUMIN, _REST_FUENTES_SUMIN, _ZOO_SUMIN),
    ),
    # Comparte Zoológico Suministros con el anterior: dos supervisores sobre la misma
    # bodega es un caso real y conviene tenerlo sembrado.
    UsuarioDemo(
        "2000000003", "Diana Carolina Pineda", RolUsuario.supervisor,
        (_ZOO_SUMIN, _ZOO),
    ),
    # ── Supernumerarios (exactamente 1 bodega) ────────────────────
    UsuarioDemo("3000000001", "Jhon Freddy Cárdenas", RolUsuario.supernumerario, (_ALMACEN_AYB,)),
    UsuarioDemo("3000000002", "Yuliana Andrea Mosquera", RolUsuario.supernumerario, (_REST_FUENTES_AYB,)),
    UsuarioDemo("3000000003", "Édinson Rivera Salcedo", RolUsuario.supernumerario, (_ALMACEN_SUMIN,)),
    UsuarioDemo("3000000004", "Leidy Johana Quintero", RolUsuario.supernumerario, (_REST_FUENTES_SUMIN,)),
    UsuarioDemo("3000000005", "Wilmar Alexis Torres", RolUsuario.supernumerario, (_KIOSCO_TAQUILLA,)),
    UsuarioDemo("3000000006", "Nubia Esperanza Galvis", RolUsuario.supernumerario, (_ZOO,)),
)


def _indice_bodegas(db: Session) -> dict[str, Bodega]:
    """Bodegas indexadas por sus dos claves naturales posibles."""
    indice: dict[str, Bodega] = {}
    for bodega in db.scalars(select(Bodega)).all():
        if bodega.slug:
            indice[f"slug:{bodega.slug}"] = bodega
        if bodega.id_erp is not None:
            indice[f"erp:{bodega.id_erp}"] = bodega
    return indice


def ensure_usuarios_demo(db: Session, password: str) -> tuple[int, int]:
    """Crea o reconcilia la plantilla. Devuelve `(creados, actualizados)`.

    Idempotente por cédula. A quien ya existe se le reconcilian nombre, rol y bodegas
    —así una corrección del roster llega con el siguiente despliegue— pero **no** la
    contraseña: si alguien la cambió con `/auth/change-password`, un despliegue no
    tiene por qué revertírsela sin avisar.
    """
    indice = _indice_bodegas(db)
    creados = actualizados = 0

    for demo in ROSTER:
        faltantes = [clave for clave in demo.bodegas if clave not in indice]
        if faltantes:
            # Fallar fuerte: seguir dejaría un supernumerario sin bodega, que es
            # justo el estado que la invariante 3 prohíbe.
            raise RuntimeError(
                f"[usuarios_demo] {demo.cedula} referencia bodegas inexistentes: {faltantes}. "
                "¿Cambió el dataset o el mapeo stock→bodega?"
            )
        bodegas = [indice[clave] for clave in demo.bodegas]

        usuario = db.scalar(select(Usuario).where(Usuario.cedula == demo.cedula))
        if usuario is None:
            db.add(
                Usuario(
                    nombre=demo.nombre,
                    cedula=demo.cedula,
                    password_hash=hash_password(password),
                    rol=demo.rol,
                    # La clave del seed es la definitiva: forzar el cambio solo estorba
                    # en la demo y ningún cliente lo exige (web y móvil leen el flag,
                    # no bloquean con él).
                    must_change_password=False,
                    bodegas=bodegas,
                )
            )
            creados += 1
            continue

        desactualizado = (
            usuario.nombre != demo.nombre
            or usuario.rol != demo.rol
            or {b.id for b in usuario.bodegas} != {b.id for b in bodegas}
        )
        if desactualizado:
            usuario.nombre = demo.nombre
            usuario.rol = demo.rol
            usuario.bodegas = bodegas
            actualizados += 1

    return creados, actualizados
