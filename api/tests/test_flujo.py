"""Flujo E2E de la Fase 1: rechazo por canal, regla de roles, concurrencia y
conteo móvil sin ERP (con recuento libre)."""
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
        json={"nombre": f"U {rol}", "cedula": ced, "password": "secret123",
              "rol": rol, "bodega_ids": bodega_ids},
    )
    assert r.status_code == 201, r.text
    return ced, r.json()


def test_login_web_rechaza_supernumerario(client, admin_token, bodega_test):
    ced, _ = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    r = client.post("/auth/login/web", json={"cedula": ced, "password": "secret123"})
    assert r.status_code == 403
    assert "vil" in r.json()["detail"].lower()  # "móvil"


def test_login_movil_rechaza_supervisor(client, admin_token, bodega_test):
    ced, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    r = client.post("/auth/login/movil", json={"cedula": ced, "password": "secret123"})
    assert r.status_code == 403


def test_supernumerario_exige_una_bodega(client, admin_token, bodega_test):
    r = client.post(
        "/usuarios",
        headers=auth(admin_token),
        json={"nombre": "X", "cedula": _cedula(), "password": "secret123",
              "rol": "supernumerario", "bodega_ids": [bodega_test, bodega_test]},
    )
    assert r.status_code == 422


def test_concurrencia_doble_asignacion(client, admin_token, bodega_test):
    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = client.post("/tomas", headers=auth(admin_token), json={"bodega_id": bodega_test}).json()["id"]

    r1 = client.post("/listados", headers=auth(admin_token),
                     json={"toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u1["id"]})
    assert r1.status_code == 201, r1.text

    r2 = client.post("/listados", headers=auth(admin_token),
                     json={"toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u2["id"]})
    assert r2.status_code == 409, r2.text


def test_flujo_movil_sin_erp_y_recuento(client, admin_token, bodega_test):
    ced, u = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = client.post("/tomas", headers=auth(admin_token), json={"bodega_id": bodega_test}).json()["id"]
    r = client.post("/listados", headers=auth(admin_token),
                    json={"toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u["id"]})
    assert r.status_code == 201, r.text

    tok = client.post("/auth/login/movil", json={"cedula": ced, "password": "secret123"}).json()["access_token"]
    r = client.get("/movil/mi-listado", headers=auth(tok))
    assert r.status_code == 200, r.text
    assert "cantidad_erp" not in r.text  # ANTI-SESGO a nivel de payload
    items = r.json()["items"]
    assert len(items) == 2

    li = items[0]["listado_item_id"]
    r1 = client.post("/movil/conteos", headers=auth(tok),
                     json={"listado_item_id": li, "cantidad_contada": 7, "metodo": "escaneo", "entrada": "voz"})
    assert r1.status_code == 201, r1.text
    assert r1.json()["intento_num"] == 1

    # Recuento libre (toma abierta) → intento 2.
    r2 = client.post("/movil/conteos", headers=auth(tok),
                     json={"listado_item_id": li, "cantidad_contada": 8, "metodo": "busqueda", "entrada": "manual"})
    assert r2.status_code == 201, r2.text
    assert r2.json()["intento_num"] == 2
