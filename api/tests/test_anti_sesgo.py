"""Test de contrato ANTI-SESGO: ningún esquema del canal /movil puede exponer
la cantidad del ERP. Se verifica sobre el OpenAPI (no sobre la UI)."""
from collections.abc import Iterator

from app.main import app


def _iter_refs(node: object) -> Iterator[str]:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            yield ref.split("/")[-1]
        for v in node.values():
            yield from _iter_refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_refs(v)


def _resolver(openapi: dict, name: str, seen: set[str]) -> None:
    if name in seen:
        return
    seen.add(name)
    comp = openapi["components"]["schemas"].get(name, {})
    for ref in _iter_refs(comp):
        _resolver(openapi, ref, seen)


def test_movil_no_expone_cantidad_erp() -> None:
    openapi = app.openapi()

    # Esquemas referenciados (transitivamente) por las rutas /movil.
    seen: set[str] = set()
    for path, item in openapi["paths"].items():
        if path.startswith("/movil"):
            for ref in _iter_refs(item):
                _resolver(openapi, ref, seen)

    props: set[str] = set()
    for name in seen:
        comp = openapi["components"]["schemas"].get(name, {})
        props |= set((comp.get("properties") or {}).keys())

    ofensores = {p for p in props if "erp" in p.lower()}
    assert not ofensores, f"El canal móvil expone campos ERP: {ofensores} (esquemas: {sorted(seen)})"


def test_web_item_si_expone_cantidad_erp() -> None:
    # Control positivo: el esquema WEB sí trae cantidad_erp (si no, el test previo sería trivial).
    openapi = app.openapi()
    item = openapi["components"]["schemas"]["ItemRead"]
    assert "cantidad_erp" in item["properties"]
