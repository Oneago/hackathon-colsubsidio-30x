"""Agregar ítems a un listado activo (ej. el supervisor olvidó incluir alguno).

Solo agrega: no hay forma de quitar ítems ya incluidos por esta vía (ver el
docstring de `agregar_items_listado` en `routers/listados.py` sobre por qué).
"""
from tests.conftest import auth
from tests.test_asignaciones import _abrir_toma, _crear_usuario


def _items_de_bodega(client, admin_token, bodega_id):
    r = client.get(f"/bodegas/{bodega_id}/items", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    return r.json()


def test_agregar_item_nuevo_a_listado_activo(client, admin_token, bodega_test):
    _, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    items = _items_de_bodega(client, admin_token, bodega_test)
    assert len(items) == 2

    r = client.post("/listados", headers=auth(admin_token),
                    json={"toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": sup["id"],
                          "item_ids": [items[0]["id"]]})
    assert r.status_code == 201, r.text
    listado = r.json()
    assert listado["total_items"] == 1

    incluidos = client.get(f"/listados/{listado['id']}/items", headers=auth(admin_token))
    assert incluidos.status_code == 200
    assert [i["id"] for i in incluidos.json()] == [items[0]["id"]]

    r = client.patch(f"/listados/{listado['id']}/items", headers=auth(admin_token),
                     json={"item_ids": [items[1]["id"]]})
    assert r.status_code == 200, r.text
    assert r.json()["total_items"] == 2


def test_agregar_items_ya_incluidos_da_422(client, admin_token, bodega_test):
    _, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    items = _items_de_bodega(client, admin_token, bodega_test)

    listado = client.post("/listados", headers=auth(admin_token),
                          json={"toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": sup["id"]}).json()

    r = client.patch(f"/listados/{listado['id']}/items", headers=auth(admin_token),
                     json={"item_ids": [items[0]["id"]]})
    assert r.status_code == 422


def test_agregar_items_a_listado_cancelado_da_409(client, admin_token, bodega_test):
    _, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    items = _items_de_bodega(client, admin_token, bodega_test)

    listado = client.post("/listados", headers=auth(admin_token),
                          json={"toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": sup["id"],
                                "item_ids": [items[0]["id"]]}).json()
    assert client.patch(f"/listados/{listado['id']}", headers=auth(admin_token),
                        json={"estado": "cancelado"}).status_code == 200

    r = client.patch(f"/listados/{listado['id']}/items", headers=auth(admin_token),
                     json={"item_ids": [items[1]["id"]]})
    assert r.status_code == 409


def test_agregar_items_con_toma_cerrada_da_409(client, admin_token, bodega_test):
    _, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    items = _items_de_bodega(client, admin_token, bodega_test)

    listado = client.post("/listados", headers=auth(admin_token),
                          json={"toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": sup["id"],
                                "item_ids": [items[0]["id"]]}).json()
    assert client.post(f"/tomas/{toma}/cerrar", headers=auth(admin_token)).status_code == 200

    r = client.patch(f"/listados/{listado['id']}/items", headers=auth(admin_token),
                     json={"item_ids": [items[1]["id"]]})
    assert r.status_code == 409
