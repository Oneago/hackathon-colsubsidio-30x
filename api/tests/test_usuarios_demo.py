"""La plantilla demo del seed corre en cada despliegue: si sembrara un usuario que
viola las reglas de rol/bodega, el sistema quedaría en un estado que la API misma
rechazaría crear por `/usuarios`. Estas pruebas cierran esa puerta.
"""
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Bodega, RolUsuario, Usuario
from app.security import hash_password, verify_password
from app.seed.usuarios_demo import ROSTER, ensure_usuarios_demo

PASSWORD = "demo1234"
CEDULAS = [d.cedula for d in ROSTER]
CLAVES = sorted({clave for d in ROSTER for clave in d.bodegas})


@pytest.fixture()
def bodegas_del_roster():
    """Crea las bodegas que el roster referencia por clave natural y limpia al salir.

    El roster apunta al dataset real, que la BD de test no carga; se sintetizan aquí
    para probar la siembra sin depender de `inventory.json`.
    """
    with SessionLocal() as db:
        for clave in CLAVES:
            tipo, valor = clave.split(":", 1)
            campo = {"slug": "slug", "erp": "id_erp"}[tipo]
            existente = db.scalar(
                select(Bodega).where(getattr(Bodega, campo) == (int(valor) if tipo == "erp" else valor))
            )
            if not existente:
                db.add(
                    Bodega(
                        nombre=f"BODEGA {clave}",
                        slug=valor if tipo == "slug" else None,
                        id_erp=int(valor) if tipo == "erp" else None,
                        es_operativa=True,
                    )
                )
        db.commit()
    yield
    with SessionLocal() as db:
        for usuario in db.scalars(select(Usuario).where(Usuario.cedula.in_(CEDULAS))).all():
            db.delete(usuario)
        db.commit()


def test_roster_respeta_reglas_de_rol_y_bodega() -> None:
    assert len(CEDULAS) == len(set(CEDULAS)), "cédulas duplicadas en el roster"
    for demo in ROSTER:
        # El admin no se siembra aquí (lo hace ensure_admin) y no persiste bodegas.
        assert demo.rol is not RolUsuario.administrador
        if demo.rol is RolUsuario.supernumerario:
            assert len(demo.bodegas) == 1, f"{demo.cedula}: supernumerario debe tener 1 bodega"
        else:
            assert len(demo.bodegas) >= 1, f"{demo.cedula}: supervisor necesita al menos 1"
        assert len(set(demo.bodegas)) == len(demo.bodegas), f"{demo.cedula}: bodega repetida"


def test_siembra_y_es_idempotente(bodegas_del_roster: None) -> None:
    with SessionLocal() as db:
        creados, actualizados = ensure_usuarios_demo(db, PASSWORD)
        db.commit()
    assert (creados, actualizados) == (len(ROSTER), 0)

    # Segunda corrida: mismo estado, sin escrituras.
    with SessionLocal() as db:
        assert ensure_usuarios_demo(db, PASSWORD) == (0, 0)
        db.commit()

        for demo in ROSTER:
            usuario = db.scalar(select(Usuario).where(Usuario.cedula == demo.cedula))
            assert usuario is not None and usuario.rol == demo.rol
            assert len(usuario.bodegas) == len(demo.bodegas)
            assert verify_password(PASSWORD, usuario.password_hash)
            # Sin cambio forzado: la clave del seed es la definitiva.
            assert usuario.must_change_password is False


def test_reconcilia_el_roster_pero_respeta_la_clave_cambiada(bodegas_del_roster: None) -> None:
    with SessionLocal() as db:
        ensure_usuarios_demo(db, PASSWORD)
        db.commit()

    # Simula deriva: alguien renombró al usuario y cambió su clave.
    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.cedula == ROSTER[0].cedula))
        usuario.nombre = "Nombre Cambiado"
        usuario.bodegas = []
        usuario.password_hash = hash_password("otraclave")
        db.commit()

    with SessionLocal() as db:
        assert ensure_usuarios_demo(db, PASSWORD) == (0, 1)
        db.commit()
        usuario = db.scalar(select(Usuario).where(Usuario.cedula == ROSTER[0].cedula))
        assert usuario.nombre == ROSTER[0].nombre
        assert len(usuario.bodegas) == len(ROSTER[0].bodegas)
        # La contraseña NO se revierte: un despliegue no pisa un cambio deliberado.
        assert verify_password("otraclave", usuario.password_hash)


def test_falla_si_el_dataset_no_trae_una_bodega_del_roster() -> None:
    with SessionLocal() as db:
        # Sin las bodegas sintéticas del fixture, resolver el roster es imposible.
        for bodega in db.scalars(select(Bodega).where(Bodega.slug.in_(
            [c.split(":", 1)[1] for c in CLAVES if c.startswith("slug:")]
        ))).all():
            db.delete(bodega)
        db.commit()
        with pytest.raises(RuntimeError, match="bodegas inexistentes"):
            ensure_usuarios_demo(db, PASSWORD)
