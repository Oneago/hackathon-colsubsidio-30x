"""Fixtures de prueba. Las pruebas corren contra una BASE DE DATOS DEDICADA
(`<POSTGRES_DB>_test`) para NO ensuciar la base de desarrollo/demo. La BD de test
se crea al vuelo y su esquema con `create_all` (sin tocar las migraciones)."""
import os

# 1) Apuntar a la BD de test ANTES de importar la app (settings lee el entorno).
_BASE_DB = os.environ.get("POSTGRES_DB", "inventario")
_TEST_DB = f"{_BASE_DB}_test"
os.environ["POSTGRES_DB"] = _TEST_DB


def _crear_bd_test() -> None:
    import psycopg
    from psycopg import errors

    conn = psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "inventario"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        dbname="postgres",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{_TEST_DB}"')
    except errors.DuplicateDatabase:
        pass
    finally:
        conn.close()


_crear_bd_test()

# 2) Importar la app (ya usa la BD de test) y crear el esquema.
import uuid  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Bodega, Item, RolUsuario, UnidadMedida, Usuario  # noqa: E402
from app.security import hash_password  # noqa: E402

Base.metadata.create_all(bind=engine)

ADMIN = {"cedula": "9999999999", "password": "adminpass"}


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_admin() -> None:
    with SessionLocal() as db:
        if not db.scalar(select(Usuario).where(Usuario.cedula == ADMIN["cedula"])):
            db.add(
                Usuario(
                    nombre="Test Admin",
                    cedula=ADMIN["cedula"],
                    password_hash=hash_password(ADMIN["password"]),
                    rol=RolUsuario.administrador,
                    must_change_password=False,
                )
            )
            db.commit()


@pytest.fixture()
def bodega_test() -> int:
    """Crea una bodega operativa nueva (única por prueba) con 2 ítems y devuelve su id."""
    marca = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        bodega = Bodega(nombre=f"BODEGA TEST {marca}", slug=f"test_{marca}", es_operativa=True)
        db.add(bodega)
        db.flush()
        db.add_all(
            [
                Item(
                    bodega_id=bodega.id, nr_articulo=None, codigo_barras=f"GEN-T{marca}A",
                    descripcion=f"ITEM A {marca}", descripcion_norm=f"ITEM A {marca}".upper(),
                    unidad=UnidadMedida.unidad, cantidad_erp=10,
                ),
                Item(
                    bodega_id=bodega.id, nr_articulo=12345, codigo_barras="12345",
                    descripcion=f"ITEM B {marca}", descripcion_norm=f"ITEM B {marca}".upper(),
                    unidad=UnidadMedida.litro, cantidad_erp=5,
                ),
            ]
        )
        db.commit()
        return bodega.id


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    r = client.post("/auth/login/web", json=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
