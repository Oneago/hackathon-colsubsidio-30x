"""Utilidades de dominio: texto de unidades es-CO, frase de confirmación (TTS) y
formato de cantidades para presentación."""
from decimal import Decimal

from app.models import UnidadMedida

# Forma plural para la etiqueta de medida (se usa en la frase de confirmación).
UNIDAD_PLURAL: dict[UnidadMedida, str] = {
    UnidadMedida.unidad: "unidades",
    UnidadMedida.kilogramo: "kilogramos",
    UnidadMedida.litro: "litros",
    UnidadMedida.porcion: "porciones",
}


def unidad_texto(unidad: UnidadMedida) -> str:
    return UNIDAD_PLURAL.get(unidad, "unidades")


def frase_confirmacion(descripcion: str, unidad: UnidadMedida) -> str:
    """Texto exacto que se pronuncia (TTS) y se muestra en pantalla en el móvil."""
    return f"Usted contará: {descripcion}, en {unidad_texto(unidad)}. Confirme para continuar."


def formatear_cantidad(valor: Decimal | float | None, decimales: int = 3) -> str:
    """Da formato a una cantidad para presentación: coma decimal, sin ceros de cola.

    `decimales` fija la escala antes de recortar (3 para cantidades ya Decimal(14,3);
    1 para diff_pct, que es float sin escala fija). None -> "" (el llamador decide el
    placeholder)."""
    if valor is None:
        return ""
    texto = f"{valor:.{decimales}f}"
    if set(texto) <= {"-", "0", "."}:  # evita el "-0" engañoso por ruido de redondeo
        texto = texto.lstrip("-")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")
