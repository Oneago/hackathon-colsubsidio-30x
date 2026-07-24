"""Utilidades de dominio: texto de unidades es-CO y frase de confirmación (TTS)."""
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
