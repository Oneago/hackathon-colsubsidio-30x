"""Fase 5: pruebas de endurecimiento (contraseñas, cierre de toma, permisos)."""
from tests.conftest import auth
from tests.test_flujo import _crear_usuario


def test_cambio_de_contrasena(client, admin_token, bodega_test):
    ced, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])

    login = client.post("/auth/login/web", json={"cedula": ced, "password": "secret123"})
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    tok = login.json()["access_token"]

    # Contraseña actual incorrecta → 400.
    mal = client.post("/auth/change-password", headers=auth(tok),
                      json={"password_actual": "xxx", "password_nueva": "nueva123"})
    assert mal.status_code == 400

    ok = client.post("/auth/change-password", headers=auth(tok),
                     json={"password_actual": "secret123", "password_nueva": "nueva123"})
    assert ok.status_code == 200

    assert client.post("/auth/login/web", json={"cedula": ced, "password": "secret123"}).status_code == 401
    relogin = client.post("/auth/login/web", json={"cedula": ced, "password": "nueva123"})
    assert relogin.status_code == 200
    assert relogin.json()["must_change_password"] is False


def test_toma_cerrada_rechaza_conteo(client, admin_token, bodega_test):
    ced, u = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = client.post("/tomas", headers=auth(admin_token), json={"bodega_id": bodega_test}).json()["id"]
    client.post("/listados", headers=auth(admin_token),
                json={"toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u["id"]})

    tok = client.post("/auth/login/movil", json={"cedula": ced, "password": "secret123"}).json()["access_token"]
    li = client.get("/movil/mi-listado", headers=auth(tok)).json()["items"][0]["listado_item_id"]

    # El admin cierra la toma; el conteo debe rechazarse.
    assert client.post(f"/tomas/{toma}/cerrar", headers=auth(admin_token)).status_code == 200
    r = client.post("/movil/conteos", headers=auth(tok),
                    json={"listado_item_id": li, "cantidad_contada": 3, "metodo": "busqueda", "entrada": "manual"})
    assert r.status_code == 409


def test_admin_restablece_contrasena(client, admin_token, bodega_test):
    ced, u = _crear_usuario(client, admin_token, "supervisor", [bodega_test])

    r = client.post(f"/usuarios/{u['id']}/reset-password", headers=auth(admin_token),
                    json={"password_nueva": "asignada9"})
    assert r.status_code == 200, r.text
    # La clave que asigna el admin es la definitiva: no se exige rotarla al ingresar.
    assert r.json()["must_change_password"] is False

    assert client.post("/auth/login/web", json={"cedula": ced, "password": "secret123"}).status_code == 401
    relogin = client.post("/auth/login/web", json={"cedula": ced, "password": "asignada9"})
    assert relogin.status_code == 200
    assert relogin.json()["must_change_password"] is False


def test_reset_password_solo_admin_y_no_a_si_mismo(client, admin_token, bodega_test):
    ced, sup = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    _, otro = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])

    tok = client.post("/auth/login/web", json={"cedula": ced, "password": "secret123"}).json()["access_token"]
    r = client.post(f"/usuarios/{otro['id']}/reset-password", headers=auth(tok),
                    json={"password_nueva": "asignada9"})
    assert r.status_code == 403

    yo = client.get("/auth/me", headers=auth(admin_token)).json()
    propio = client.post(f"/usuarios/{yo['id']}/reset-password", headers=auth(admin_token),
                         json={"password_nueva": "asignada9"})
    assert propio.status_code == 400

    corta = client.post(f"/usuarios/{sup['id']}/reset-password", headers=auth(admin_token),
                        json={"password_nueva": "123"})
    assert corta.status_code == 422


def test_supervisor_no_puede_crear_usuarios(client, admin_token, bodega_test):
    ced, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    tok = client.post("/auth/login/web", json={"cedula": ced, "password": "secret123"}).json()["access_token"]
    r = client.post("/usuarios", headers=auth(tok),
                    json={"nombre": "X", "cedula": "1", "password": "secret123",
                          "rol": "supervisor", "bodega_ids": [bodega_test]})
    assert r.status_code == 403
