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

    # Exportación CSV: delimitador ";" y coma decimal (convención Excel es-CO),
    # sin ceros de cola ("10" en vez de "10.000").
    csv_res = client.get(f"/reportes/comparacion.csv?toma_id={toma}", headers=auth(admin_token))
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "cantidad_erp" in csv_res.text

    filas_csv = csv_res.text.lstrip("﻿").splitlines()
    assert filas_csv[0].split(";") == [
        "codigo", "descripcion", "unidad", "cantidad_erp", "cantidad_contada",
        "diff_abs", "diff_pct", "critico", "estado",
    ]
    linea_contada = next(
        l for l in filas_csv[1:] if l.split(";")[0] == contada["codigo_barras"]
    )
    campos = linea_contada.split(";")
    assert campos[3] == "10"   # cantidad_erp sin ".000"
    assert campos[4] == "7"    # cantidad_contada sin ".000"
    assert campos[5] == "-3"   # diff_abs
    assert campos[6] == "-30"  # diff_pct a 1 decimal, sin ".0"


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


def test_comparacion_no_duplica_con_dos_listados_activos_disjuntos(client, admin_token, bodega_test):
    """Dos supernumerarios contando la misma bodega en paralelo (ítems
    disjuntos) no deben producir filas duplicadas ni omitidas en el informe."""
    from tests.test_asignaciones import _abrir_toma

    _, u1 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    _, u2 = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    toma = _abrir_toma(client, admin_token, bodega_test)

    item_a, item_b = (
        i["id"] for i in client.get(f"/bodegas/{bodega_test}/items", headers=auth(admin_token)).json()
    )
    r1 = client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u1["id"], "item_ids": [item_a],
    })
    assert r1.status_code == 201, r1.text
    r2 = client.post("/listados", headers=auth(admin_token), json={
        "toma_id": toma, "bodega_id": bodega_test, "supernumerario_id": u2["id"], "item_ids": [item_b],
    })
    assert r2.status_code == 201, r2.text

    comp = client.get(f"/reportes/comparacion?toma_id={toma}", headers=auth(admin_token)).json()
    assert comp["resumen"]["total_items"] == 2
    codigos = [f["codigo_barras"] for f in comp["filas"]]
    assert len(codigos) == len(set(codigos)) == 2
