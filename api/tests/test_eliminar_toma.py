"""Eliminar una toma (deshacer un error: bodega equivocada, prueba, duplicado).

Sin restricción por estado ni por conteos ya registrados (decisión de producto);
el ON DELETE CASCADE de la FK se encarga del resto. Cubre también el alcance por
bodega, igual que abrir/cerrar toma.
"""
import uuid

from app.db import SessionLocal
from app.models import Bodega, Item, UnidadMedida
from tests.conftest import auth
from tests.test_asignaciones import _abrir_toma, _asignar, _cedula, _crear_usuario


def _crear_bodega() -> int:
    marca = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        bodega = Bodega(nombre=f"BODEGA AJENA {marca}", slug=f"ajena_{marca}", es_operativa=True)
        db.add(bodega)
        db.flush()
        db.add(
            Item(
                bodega_id=bodega.id, nr_articulo=None, codigo_barras=f"GEN-A{marca}",
                descripcion=f"ITEM {marca}", descripcion_norm=f"ITEM {marca}".upper(),
                unidad=UnidadMedida.unidad, cantidad_erp=1,
            )
        )
        db.commit()
        return bodega.id


def test_eliminar_toma_borra_en_cascada_listados_items_conteos(client, admin_token, bodega_test):
    ced, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    listado = _asignar(client, admin_token, toma, bodega_test, sup["id"]).json()

    tok = client.post("/auth/login/movil", json={"cedula": ced, "password": "secret123"}).json()["access_token"]
    li = client.get("/movil/mi-listado", headers=auth(tok)).json()["items"][0]["listado_item_id"]
    r = client.post("/movil/conteos", headers=auth(tok),
                    json={"listado_item_id": li, "cantidad_contada": 3, "metodo": "busqueda", "entrada": "manual"})
    assert r.status_code == 201, r.text

    r = client.delete(f"/tomas/{toma}", headers=auth(admin_token))
    assert r.status_code == 204, r.text

    assert client.get(f"/listados/{listado['id']}", headers=auth(admin_token)).status_code == 404
    tomas_restantes = client.get("/tomas", headers=auth(admin_token)).json()
    assert toma not in {t["id"] for t in tomas_restantes}


def test_eliminar_toma_sin_restriccion_de_estado(client, admin_token, bodega_test):
    abierta = _abrir_toma(client, admin_token, bodega_test)
    assert client.delete(f"/tomas/{abierta}", headers=auth(admin_token)).status_code == 204

    cerrada = _abrir_toma(client, admin_token, bodega_test)
    assert client.post(f"/tomas/{cerrada}/cerrar", headers=auth(admin_token)).status_code == 200
    assert client.delete(f"/tomas/{cerrada}", headers=auth(admin_token)).status_code == 204


def test_eliminar_toma_inexistente_da_404(client, admin_token):
    assert client.delete("/tomas/999999999", headers=auth(admin_token)).status_code == 404


def test_supervisor_elimina_toma_de_su_bodega(client, admin_token, bodega_test):
    ced_sup, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    tok = client.post("/auth/login/web", json={"cedula": ced_sup, "password": "secret123"}).json()["access_token"]
    toma = _abrir_toma(client, admin_token, bodega_test)

    assert client.delete(f"/tomas/{toma}", headers=auth(tok)).status_code == 204


def test_supervisor_no_elimina_toma_de_bodega_ajena(client, admin_token, bodega_test):
    ced_sup, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    tok = client.post("/auth/login/web", json={"cedula": ced_sup, "password": "secret123"}).json()["access_token"]

    ajena = _crear_bodega()
    toma = _abrir_toma(client, admin_token, ajena)

    assert client.delete(f"/tomas/{toma}", headers=auth(tok)).status_code == 403
