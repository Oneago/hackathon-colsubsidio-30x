"""Reabrir una toma cerrada por error, antes de terminar los conteos.

No revive los listados que quedaron `completado` al cerrarla (se reactivan a
mano vía PATCH /listados/{id}); solo revierte el estado de la toma.
"""
from tests.test_asignaciones import _abrir_toma, _asignar, _crear_usuario
from tests.test_eliminar_toma import _crear_bodega
from tests.conftest import auth


def test_reabrir_toma_cerrada(client, admin_token, bodega_test):
    toma = _abrir_toma(client, admin_token, bodega_test)
    assert client.post(f"/tomas/{toma}/cerrar", headers=auth(admin_token)).status_code == 200

    r = client.post(f"/tomas/{toma}/reabrir", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "abierta"
    assert r.json()["fecha_cierre"] is None


def test_reabrir_toma_ya_abierta_da_409(client, admin_token, bodega_test):
    toma = _abrir_toma(client, admin_token, bodega_test)
    r = client.post(f"/tomas/{toma}/reabrir", headers=auth(admin_token))
    assert r.status_code == 409


def test_reabrir_toma_con_otra_abierta_en_la_bodega_da_409(client, admin_token, bodega_test):
    cerrada = _abrir_toma(client, admin_token, bodega_test)
    assert client.post(f"/tomas/{cerrada}/cerrar", headers=auth(admin_token)).status_code == 200
    _abrir_toma(client, admin_token, bodega_test)  # nueva toma abierta ocupa la bodega

    r = client.post(f"/tomas/{cerrada}/reabrir", headers=auth(admin_token))
    assert r.status_code == 409


def test_reabrir_toma_inexistente_da_404(client, admin_token):
    assert client.post("/tomas/999999999/reabrir", headers=auth(admin_token)).status_code == 404


def test_reabrir_permite_reactivar_listado_completado(client, admin_token, bodega_test):
    _, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    listado = _asignar(client, admin_token, toma, bodega_test, sup["id"]).json()
    assert client.post(f"/tomas/{toma}/cerrar", headers=auth(admin_token)).status_code == 200
    assert client.get(f"/listados/{listado['id']}", headers=auth(admin_token)).json()["estado"] == "completado"

    assert client.post(f"/tomas/{toma}/reabrir", headers=auth(admin_token)).status_code == 200

    r = client.patch(f"/listados/{listado['id']}", headers=auth(admin_token), json={"estado": "activo"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "activo"


def test_supervisor_no_reabre_toma_de_bodega_ajena(client, admin_token, bodega_test):
    ced_sup, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    tok = client.post("/auth/login/web", json={"cedula": ced_sup, "password": "secret123"}).json()["access_token"]

    ajena = _crear_bodega()
    toma = _abrir_toma(client, admin_token, ajena)
    assert client.post(f"/tomas/{toma}/cerrar", headers=auth(admin_token)).status_code == 200

    assert client.post(f"/tomas/{toma}/reabrir", headers=auth(tok)).status_code == 403
