"""Ciclo de vida de la asignación a supernumerarios.

Cubre lo que el 409 de concurrencia dejaba sin salida: reasignar, cancelar, y
que cerrar la toma libere de verdad al supernumerario.
"""
import uuid

from fastapi.testclient import TestClient

from tests.conftest import auth


def _cedula() -> str:
    return str(uuid.uuid4().int)[:10]


def _crear_usuario(client: TestClient, token: str, rol: str, bodega_ids: list[int]) -> tuple[str, dict]:
    ced = _cedula()
    r = client.post(
        "/usuarios",
        headers=auth(token),
        json={"nombre": f"U {rol} {ced[:4]}", "cedula": ced, "password": "secret123",
              "rol": rol, "bodega_ids": bodega_ids},
    )
    assert r.status_code == 201, r.text
    return ced, r.json()


def _abrir_toma(client: TestClient, token: str, bodega_id: int) -> int:
    r = client.post("/tomas", headers=auth(token), json={"bodega_id": bodega_id})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _asignar(client: TestClient, token: str, toma: int, bodega: int, sup: int):
    return client.post("/listados", headers=auth(token),
                       json={"toma_id": toma, "bodega_id": bodega, "supernumerario_id": sup})


def test_conflicto_nombra_al_supernumerario_actual(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    assert _asignar(client, admin_token, toma, bodega_test, u1["id"]).status_code == 201

    r = _asignar(client, admin_token, toma, bodega_test, u2["id"])
    assert r.status_code == 409
    detalle = r.json()["detail"]
    # El mensaje tiene que decir QUIÉN ocupa la bodega y cómo liberarla; el
    # texto anónimo anterior dejaba al supervisor sin acción posible.
    assert u1["nombre"] in detalle
    assert "cancél" in detalle.lower() or "reasigne" in detalle.lower()


def test_reasignar_listado_a_otro_supernumerario(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    listado = _asignar(client, admin_token, toma, bodega_test, u1["id"]).json()

    r = client.patch(f"/listados/{listado['id']}", headers=auth(admin_token),
                     json={"supernumerario_id": u2["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["supernumerario_id"] == u2["id"]
    assert r.json()["supernumerario_nombre"] == u2["nombre"]
    assert r.json()["estado"] == "activo"


def test_cancelar_libera_la_bodega(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    listado = _asignar(client, admin_token, toma, bodega_test, u1["id"]).json()

    r = client.patch(f"/listados/{listado['id']}", headers=auth(admin_token), json={"estado": "cancelado"})
    assert r.status_code == 200, r.text
    # Con el listado cancelado, la misma bodega vuelve a ser asignable.
    assert _asignar(client, admin_token, toma, bodega_test, u2["id"]).status_code == 201


def test_supernumerario_no_acumula_dos_listados_vigentes(client, admin_token, bodega_test):
    """El móvil solo entrega UN listado: dos asignaciones vigentes esconderían una."""
    _, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma_a = _abrir_toma(client, admin_token, bodega_test)
    assert _asignar(client, admin_token, toma_a, bodega_test, sup["id"]).status_code == 201

    # Segunda bodega para el mismo supernumerario, en otra toma abierta.
    otra = client.post(
        "/usuarios", headers=auth(admin_token),
        json={"nombre": "tmp", "cedula": _cedula(), "password": "secret123",
              "rol": "supernumerario", "bodega_ids": [bodega_test]},
    )
    assert otra.status_code == 201

    client.post(f"/tomas/{toma_a}/cerrar", headers=auth(admin_token))
    toma_b = _abrir_toma(client, admin_token, bodega_test)
    # Tras cerrar la toma A el supernumerario queda libre: la nueva sí entra.
    assert _asignar(client, admin_token, toma_b, bodega_test, sup["id"]).status_code == 201


def test_cerrar_toma_completa_sus_listados(client, admin_token, bodega_test):
    ced, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    listado = _asignar(client, admin_token, toma, bodega_test, sup["id"]).json()

    assert client.post(f"/tomas/{toma}/cerrar", headers=auth(admin_token)).status_code == 200

    r = client.get(f"/listados/{listado['id']}", headers=auth(admin_token))
    assert r.json()["estado"] == "completado"

    # Y el móvil ya no lo entrega: un listado de toma cerrada no es contable.
    tok = client.post("/auth/login/movil", json={"cedula": ced, "password": "secret123"}).json()["access_token"]
    assert client.get("/movil/mi-listado", headers=auth(tok)).status_code == 404


def test_no_se_modifica_listado_de_toma_cerrada(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    listado = _asignar(client, admin_token, toma, bodega_test, u1["id"]).json()
    client.post(f"/tomas/{toma}/cerrar", headers=auth(admin_token))

    r = client.patch(f"/listados/{listado['id']}", headers=auth(admin_token),
                     json={"supernumerario_id": u2["id"]})
    assert r.status_code == 409


def test_supervisor_lista_supernumerarios_de_sus_bodegas(client, admin_token, bodega_test):
    """Sin esta ruta el supervisor no puede poblar el desplegable y no asigna nada."""
    ced_sup, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    _, esperado = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    tok = client.post("/auth/login/web", json={"cedula": ced_sup, "password": "secret123"}).json()["access_token"]

    # La plantilla completa le sigue estando vedada.
    assert client.get("/usuarios", headers=auth(tok)).status_code == 403

    r = client.get(f"/usuarios/supernumerarios?bodega_id={bodega_test}", headers=auth(tok))
    assert r.status_code == 200, r.text
    ids = [u["id"] for u in r.json()]
    assert esperado["id"] in ids
    assert all(u["rol"] == "supernumerario" for u in r.json())


def test_supervisor_no_ve_supernumerarios_de_bodega_ajena(client, admin_token, bodega_test):
    ced_sup, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    ajena = client.post(
        "/usuarios", headers=auth(admin_token),
        json={"nombre": "ajeno", "cedula": _cedula(), "password": "secret123",
              "rol": "supervisor", "bodega_ids": [bodega_test]},
    )
    assert ajena.status_code == 201
    tok = client.post("/auth/login/web", json={"cedula": ced_sup, "password": "secret123"}).json()["access_token"]
    r = client.get("/usuarios/supernumerarios?bodega_id=999999", headers=auth(tok))
    assert r.status_code == 403
