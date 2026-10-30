from decimal import Decimal

import pytest

from regalias.registro import ErrorRegistro, normalizar_isrc, validar_porcentajes


def test_porcentajes_que_suman_100_son_validos():
    validar_porcentajes([("a", Decimal("60")), ("b", Decimal("40"))])


def test_porcentajes_que_suman_99_99_se_rechazan_con_error_claro():
    with pytest.raises(ErrorRegistro, match="100"):
        validar_porcentajes([("a", Decimal("60")), ("b", Decimal("39.99"))])


def test_porcentajes_que_suman_mas_de_100_se_rechazan():
    with pytest.raises(ErrorRegistro, match="100"):
        validar_porcentajes([("a", Decimal("60")), ("b", Decimal("40.01"))])


def test_porcentaje_negativo_se_rechaza():
    with pytest.raises(ErrorRegistro):
        validar_porcentajes([("a", Decimal("110")), ("b", Decimal("-10"))])


def test_porcentaje_con_mas_de_dos_decimales_se_rechaza():
    with pytest.raises(ErrorRegistro):
        validar_porcentajes([("a", Decimal("33.333")), ("b", Decimal("66.667"))])


def test_isrc_valido_se_normaliza():
    assert normalizar_isrc("US-RC1-76-07839") == "USRC17607839"
    assert normalizar_isrc("usrc17607839") == "USRC17607839"


def test_isrc_none_es_valido_por_ser_opcional():
    assert normalizar_isrc(None) is None


@pytest.mark.parametrize("isrc", ["USRC1760783", "12RC17607839", "USRC1760783X"])
def test_isrc_invalido_se_rechaza(isrc):
    with pytest.raises(ErrorRegistro):
        normalizar_isrc(isrc)
