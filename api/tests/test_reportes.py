"""Fase 4: comparación ERP vs. conteo y exportación CSV."""
from tests.conftest import auth
from tests.test_flujo import _crear_usuario


def test_comparacion_diferencias_y_csv(client, admin_token, bodega_test):
    # bodega_test: ITEM A (erp=10, unidad) e ITEM B (erp=5, litro), ordenados A, B.
    ced, u = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = client.post("/tomas", headers=auth(admin_token), json={"bodega_id": bodega_test}).json()["id"]
    r = client.post("/listados", headers=auth(admin_token),
                    json={"toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u["id"]})
    assert r.status_code == 201, r.text

    tok = client.post("/auth/login/movil", json={"cedula": ced, "password": "secret123"}).json()["access_token"]
    items = client.get("/movil/mi-listado", headers=auth(tok)).json()["items"]

    # Cuenta solo el primer ítem (ERP=10) con 7 → Δ -3, -30% → crítico.
    li0 = items[0]["listado_item_id"]
    client.post("/movil/conteos", headers=auth(tok),
                json={"listado_item_id": li0, "cantidad_contada": 7, "metodo": "escaneo", "entrada": "manual"})

    comp = client.get(f"/reportes/comparacion?toma_id={toma}", headers=auth(admin_token))
    assert comp.status_code == 200, comp.text
    body = comp.json()
    assert body["resumen"]["total_items"] == 2
    assert body["resumen"]["contados"] == 1
    assert body["resumen"]["pendientes"] == 1
    assert body["resumen"]["criticos"] == 1

    contada = next(f for f in body["filas"] if f["contado"])
    assert float(contada["cantidad_contada"]) == 7
    assert float(contada["diff_abs"]) == -3
    assert round(contada["diff_pct"]) == -30
    assert contada["critico"] is True

    pendiente = next(f for f in body["filas"] if not f["contado"])
    assert pendiente["cantidad_contada"] is None
    assert pendiente["critico"] is False

    # Exportación CSV.
    csv_res = client.get(f"/reportes/comparacion.csv?toma_id={toma}", headers=auth(admin_token))
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "cantidad_erp" in csv_res.text


def test_comparacion_ignora_listados_cancelados(client, admin_token, bodega_test):
    """Cancelar una asignación no debe duplicar las líneas del informe."""
    from tests.test_asignaciones import _abrir_toma, _asignar

    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)

    primero = _asignar(client, admin_token, toma, bodega_test, u1["id"]).json()
    base = client.get(f"/reportes/comparacion?toma_id={toma}", headers=auth(admin_token)).json()

    client.patch(f"/listados/{primero['id']}", headers=auth(admin_token), json={"estado": "cancelado"})
    assert _asignar(client, admin_token, toma, bodega_test, u2["id"]).status_code == 201

    despues = client.get(f"/reportes/comparacion?toma_id={toma}", headers=auth(admin_token)).json()
    assert despues["resumen"]["total_items"] == base["resumen"]["total_items"]
    codigos = [f["codigo_barras"] for f in despues["filas"]]
    assert len(codigos) == len(set(codigos)), "hay ítems repetidos en el informe"
