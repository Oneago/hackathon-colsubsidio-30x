"""Formato de cantidades para presentación (coma decimal, sin ceros de cola)."""
from decimal import Decimal

from app.util import formatear_cantidad


def test_formatear_cantidad_recorta_ceros_de_cola():
    assert formatear_cantidad(Decimal("10.000")) == "10"
    assert formatear_cantidad(Decimal("1547.000")) == "1547"
    assert formatear_cantidad(Decimal("0.000")) == "0"


def test_formatear_cantidad_conserva_decimales_significativos():
    assert formatear_cantidad(Decimal("5.483")) == "5,483"
    assert formatear_cantidad(Decimal("5.900")) == "5,9"
    assert formatear_cantidad(Decimal("5.480")) == "5,48"


def test_formatear_cantidad_usa_coma_no_punto():
    resultado = formatear_cantidad(Decimal("5.483"))
    assert "," in resultado
    assert "." not in resultado


def test_formatear_cantidad_none_devuelve_vacio():
    assert formatear_cantidad(None) == ""


def test_formatear_cantidad_negativos():
    assert formatear_cantidad(Decimal("-3.000")) == "-3"
    assert formatear_cantidad(-30.0, decimales=1) == "-30"


def test_formatear_cantidad_evita_menos_cero():
    # diff_pct muy pequeño y negativo (ruido de redondeo) no debe mostrarse como "-0".
    assert formatear_cantidad(-0.04, decimales=1) == "0"
    assert formatear_cantidad(Decimal("-0.0004"), decimales=3) == "0"


def test_formatear_cantidad_decimales_variable_para_porcentaje():
    assert formatear_cantidad(-30.0, decimales=1) == "-30"
    assert formatear_cantidad(33.333333, decimales=1) == "33,3"
