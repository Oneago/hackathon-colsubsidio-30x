"""Varios listados ACTIVOS en paralelo para la misma (toma, bodega).

La invariante de "un solo listado activo por bodega" se reemplaza por "sin
ítems repetidos entre listados activos de una misma toma": varios
supernumerarios pueden contar la misma bodega a la vez si cada uno tiene un
subconjunto de ítems distinto.
"""
from tests.conftest import auth
from tests.test_asignaciones import _abrir_toma, _crear_usuario


def _items(client, admin_token, bodega_id, toma_id=None):
    url = f"/bodegas/{bodega_id}/items"
    if toma_id is not None:
        url += f"?toma_id={toma_id}"
    r = client.get(url, headers=auth(admin_token))
    assert r.status_code == 200, r.text
    return r.json()


def test_dos_listados_activos_con_items_disjuntos(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    item_a, item_b = (i["id"] for i in _items(client, admin_token, bodega_test))

    r1 = client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u1["id"], "item_ids": [item_a],
    })
    assert r1.status_code == 201, r1.text

    r2 = client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u2["id"], "item_ids": [item_b],
    })
    assert r2.status_code == 201, r2.text
    assert r1.json()["estado"] == r2.json()["estado"] == "activo"


def test_crear_con_items_solapados_da_409_nombrando_conflicto(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    item_a, item_b = (i["id"] for i in _items(client, admin_token, bodega_test))

    l1 = client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u1["id"], "item_ids": [item_a, item_b],
    })
    assert l1.status_code == 201, l1.text

    r = client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u2["id"], "item_ids": [item_a],
    })
    assert r.status_code == 409, r.text
    detalle = r.json()["detail"]
    assert u1["nombre"] in detalle
    assert f"#{l1.json()['id']}" in detalle


def test_agregar_items_solapados_da_409(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    item_a, item_b = (i["id"] for i in _items(client, admin_token, bodega_test))

    l1 = client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u1["id"], "item_ids": [item_a],
    }).json()
    client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u2["id"], "item_ids": [item_b],
    })

    # u1 intenta agregarse el ítem que ya tiene u2.
    r = client.patch(f"/listados/{l1['id']}/items", headers=auth(admin_token), json={"item_ids": [item_b]})
    assert r.status_code == 409, r.text
    assert u2["nombre"] in r.json()["detail"]


def test_reactivar_con_items_solapados_da_409(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    item_a, item_b = (i["id"] for i in _items(client, admin_token, bodega_test))

    l1 = client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u1["id"], "item_ids": [item_a, item_b],
    }).json()
    assert client.post(f"/tomas/{toma}/cerrar", headers=auth(admin_token)).status_code == 200
    assert client.post(f"/tomas/{toma}/reabrir", headers=auth(admin_token)).status_code == 200

    # Con la toma reabierta y l1 "completado", queda libre para un segundo listado.
    l2 = client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u2["id"], "item_ids": [item_a],
    })
    assert l2.status_code == 201, l2.text

    r = client.patch(f"/listados/{l1['id']}", headers=auth(admin_token), json={"estado": "activo"})
    assert r.status_code == 409, r.text
    assert u2["nombre"] in r.json()["detail"]


def test_items_disponibles_excluye_los_tomados(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    item_a, item_b = (i["id"] for i in _items(client, admin_token, bodega_test))

    assert len(_items(client, admin_token, bodega_test, toma_id=toma)) == 2

    client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u1["id"], "item_ids": [item_a],
    })

    disponibles = _items(client, admin_token, bodega_test, toma_id=toma)
    assert [i["id"] for i in disponibles] == [item_b]
    # Sin toma_id, sigue trayendo todos los ítems de la bodega (uso web general).
    assert len(_items(client, admin_token, bodega_test)) == 2
