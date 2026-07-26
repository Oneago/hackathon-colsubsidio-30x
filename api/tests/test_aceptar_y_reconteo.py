"""Las dos salidas de la comparación ERP vs. conteo: aceptar el inventario o
devolverlo a campo pidiendo reconteo.

Son excluyentes: pedir reconteo borra la aceptación previa, porque lo aprobado
fue un conteo que está a punto de cambiar.
"""
from tests.conftest import auth
from tests.test_asignaciones import _abrir_toma, _asignar, _crear_usuario
from tests.test_eliminar_toma import _crear_bodega


def _cerrar(client, token, toma):
    assert client.post(f"/tomas/{toma}/cerrar", headers=auth(token)).status_code == 200


# ── Aceptar ────────────────────────────────────────────────────


def test_aceptar_sella_quien_y_cuando(client, admin_token, bodega_test):
    toma = _abrir_toma(client, admin_token, bodega_test)
    _cerrar(client, admin_token, toma)

    r = client.post(f"/tomas/{toma}/aceptar", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["aceptada_en"] is not None
    assert body["aceptada_por"] is not None
    assert body["aceptada_por_nombre"]
    # Aceptar no cambia el ciclo de conteo: la toma sigue cerrada.
    assert body["estado"] == "cerrada"


def test_aceptar_persiste_y_se_ve_en_el_listado(client, admin_token, bodega_test):
    toma = _abrir_toma(client, admin_token, bodega_test)
    _cerrar(client, admin_token, toma)
    client.post(f"/tomas/{toma}/aceptar", headers=auth(admin_token))

    fila = next(t for t in client.get("/tomas", headers=auth(admin_token)).json() if t["id"] == toma)
    assert fila["aceptada_en"] is not None
    assert fila["aceptada_por_nombre"]


def test_no_se_acepta_una_toma_abierta(client, admin_token, bodega_test):
    toma = _abrir_toma(client, admin_token, bodega_test)
    r = client.post(f"/tomas/{toma}/aceptar", headers=auth(admin_token))
    assert r.status_code == 409
    assert "cerrada" in r.json()["detail"].lower()


def test_aceptar_dos_veces_da_409(client, admin_token, bodega_test):
    toma = _abrir_toma(client, admin_token, bodega_test)
    _cerrar(client, admin_token, toma)
    assert client.post(f"/tomas/{toma}/aceptar", headers=auth(admin_token)).status_code == 200

    r = client.post(f"/tomas/{toma}/aceptar", headers=auth(admin_token))
    assert r.status_code == 409


def test_aceptar_toma_inexistente_da_404(client, admin_token):
    assert client.post("/tomas/999999999/aceptar", headers=auth(admin_token)).status_code == 404


def test_supervisor_no_acepta_toma_de_bodega_ajena(client, admin_token, bodega_test):
    ced, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    tok = client.post("/auth/login/web", json={"cedula": ced, "password": "secret123"}).json()["access_token"]

    ajena = _crear_bodega()
    toma = _abrir_toma(client, admin_token, ajena)
    _cerrar(client, admin_token, toma)

    assert client.post(f"/tomas/{toma}/aceptar", headers=auth(tok)).status_code == 403


# ── Solicitar reconteo ─────────────────────────────────────────


def test_reconteo_reabre_la_toma_y_revive_sus_listados(client, admin_token, bodega_test):
    _, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)
    listado = _asignar(client, admin_token, toma, bodega_test, sup["id"]).json()
    _cerrar(client, admin_token, toma)
    assert client.get(f"/listados/{listado['id']}", headers=auth(admin_token)).json()["estado"] == "completado"

    r = client.post(f"/tomas/{toma}/solicitar-reconteo", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "abierta"
    assert r.json()["fecha_cierre"] is None
    # Lo que distingue a esta acción de `reabrir`: el listado vuelve a campo solo.
    assert client.get(f"/listados/{listado['id']}", headers=auth(admin_token)).json()["estado"] == "activo"


def test_reconteo_borra_la_aceptacion_previa(client, admin_token, bodega_test):
    toma = _abrir_toma(client, admin_token, bodega_test)
    _cerrar(client, admin_token, toma)
    assert client.post(f"/tomas/{toma}/aceptar", headers=auth(admin_token)).status_code == 200

    r = client.post(f"/tomas/{toma}/solicitar-reconteo", headers=auth(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["aceptada_en"] is None
    assert r.json()["aceptada_por"] is None


def test_reabrir_tambien_borra_la_aceptacion(client, admin_token, bodega_test):
    toma = _abrir_toma(client, admin_token, bodega_test)
    _cerrar(client, admin_token, toma)
    client.post(f"/tomas/{toma}/aceptar", headers=auth(admin_token))

    r = client.post(f"/tomas/{toma}/reabrir", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["aceptada_en"] is None


def test_reconteo_de_toma_abierta_da_409(client, admin_token, bodega_test):
    toma = _abrir_toma(client, admin_token, bodega_test)
    assert client.post(f"/tomas/{toma}/solicitar-reconteo", headers=auth(admin_token)).status_code == 409


def test_reconteo_bloqueado_si_el_supernumerario_ya_tiene_otra_asignacion(
    client, admin_token, bodega_test
):
    """Invariante 7: el móvil entrega un solo listado, así que revivir uno cuando
    el supernumerario ya tiene otro vigente escondería una asignación."""
    otra_bodega = _crear_bodega()
    _, sup = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])

    toma = _abrir_toma(client, admin_token, bodega_test)
    _asignar(client, admin_token, toma, bodega_test, sup["id"])
    _cerrar(client, admin_token, toma)

    # El mismo supernumerario recibe otra asignación mientras la toma está cerrada.
    client.patch(
        f"/usuarios/{sup['id']}", headers=auth(admin_token), json={"bodega_ids": [otra_bodega]}
    )
    toma2 = _abrir_toma(client, admin_token, otra_bodega)
    assert _asignar(client, admin_token, toma2, otra_bodega, sup["id"]).status_code == 201

    r = client.post(f"/tomas/{toma}/solicitar-reconteo", headers=auth(admin_token))
    assert r.status_code == 409
    assert "reconteo" in r.json()["detail"].lower()
    # Nada a medias: la toma sigue cerrada.
    fila = next(t for t in client.get("/tomas", headers=auth(admin_token)).json() if t["id"] == toma)
    assert fila["estado"] == "cerrada"


def test_reconteo_toma_inexistente_da_404(client, admin_token):
    assert client.post("/tomas/999999999/solicitar-reconteo", headers=auth(admin_token)).status_code == 404


def test_supervisor_no_pide_reconteo_de_bodega_ajena(client, admin_token, bodega_test):
    ced, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    tok = client.post("/auth/login/web", json={"cedula": ced, "password": "secret123"}).json()["access_token"]

    ajena = _crear_bodega()
    toma = _abrir_toma(client, admin_token, ajena)
    _cerrar(client, admin_token, toma)

    assert client.post(f"/tomas/{toma}/solicitar-reconteo", headers=auth(tok)).status_code == 403
