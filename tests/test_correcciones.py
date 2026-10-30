from decimal import Decimal

import pytest

from regalias.almacen import Almacen
from regalias.dinero import a_dinero, a_tasa, repartir
from regalias.registro import (
    ErrorRegistro,
    registrar_cancion,
    registrar_persona,
    registrar_venta,
    validar_porcentajes,
)
from regalias.reportes import ingresos_por_colaborador


@pytest.fixture
def almacen():
    with Almacen(":memory:") as a:
        registrar_persona(a, "ana@x.com", "Ana")
        registrar_persona(a, "ana2@x.com", "Ana")
        registrar_persona(a, "beto@x.com", "Beto")
        yield a


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "-Infinity", "sNaN", "abc", "1E+30"])
def test_a_dinero_rechaza_valores_no_finitos_invalidos_o_fuera_de_rango(valor):
    with pytest.raises(ValueError):
        a_dinero(valor)


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "abc"])
def test_a_tasa_rechaza_valores_no_finitos_o_invalidos(valor):
    with pytest.raises(ValueError):
        a_tasa(valor)


def test_repartir_rechaza_porcentajes_que_no_suman_100():
    with pytest.raises(ValueError, match="100"):
        repartir(Decimal("10.00"), [("a", Decimal("60")), ("b", Decimal("30"))])


def test_repartir_rechaza_total_con_fraccion_de_centavo():
    with pytest.raises(ValueError):
        repartir(Decimal("10.005"), [("a", Decimal("100"))])


def test_repartir_rechaza_total_negativo():
    with pytest.raises(ValueError):
        repartir(Decimal("-1.00"), [("a", Decimal("100"))])


def test_porcentaje_con_ceros_finales_es_valido():
    validar_porcentajes([("a", Decimal("50.000")), ("b", Decimal("50"))])


@pytest.mark.parametrize("pct", [Decimal("NaN"), Decimal("Infinity"), Decimal("1E+30")])
def test_porcentajes_no_finitos_o_fuera_de_rango_se_rechazan(pct):
    with pytest.raises(ErrorRegistro):
        validar_porcentajes([("a", pct), ("b", Decimal("50"))])


def test_isrc_duplicado_se_rechaza_con_error_de_registro(almacen):
    registrar_cancion(almacen, "Sol", "Ana", "USRC17607839", [("ana@x.com", Decimal("100"))])
    with pytest.raises(ErrorRegistro, match="ISRC"):
        registrar_cancion(
            almacen, "Luna", "Ana", "US-RC1-76-07839", [("ana@x.com", Decimal("100"))]
        )
    assert len(almacen.listar_canciones()) == 1


def test_identificadores_se_comparan_sin_espacios_ni_mayusculas(almacen):
    cid = registrar_cancion(
        almacen, "Sol", "Ana", None, [("ANA@x.com ", Decimal("50")), ("beto@x.com", Decimal("50"))]
    )
    registrar_venta(almacen, cid, "2026-03-02", Decimal("10.00"))
    otra = registrar_cancion(almacen, "Luna", "Ana", None, [(" ana@X.com", Decimal("100"))])
    registrar_venta(almacen, otra, "2026-03-09", Decimal("20.00"))

    assert ingresos_por_colaborador(almacen, "Ana@x.com") == {"2026-03": Decimal("25.00")}


def test_identificador_repetido_sin_distinguir_mayusculas_se_rechaza(almacen):
    with pytest.raises(ErrorRegistro):
        registrar_cancion(
            almacen, "Sol", "Ana", None,
            [("ana@x.com", Decimal("50")), ("ANA@x.com ", Decimal("50"))],
        )


def test_homonimos_con_distinto_identificador_no_se_mezclan(almacen):
    primera = registrar_cancion(almacen, "Sol", "Ana", None, [("ana@x.com", Decimal("100"))])
    segunda = registrar_cancion(almacen, "Luna", "Ana", None, [("ana2@x.com", Decimal("100"))])
    registrar_venta(almacen, primera, "2026-03-02", Decimal("10.00"))
    registrar_venta(almacen, segunda, "2026-03-02", Decimal("20.00"))

    assert ingresos_por_colaborador(almacen, "ana@x.com") == {"2026-03": Decimal("10.00")}
    assert ingresos_por_colaborador(almacen, "ana2@x.com") == {"2026-03": Decimal("20.00")}


def test_dos_homonimos_pueden_compartir_una_cancion(almacen):
    cid = registrar_cancion(
        almacen, "Duo", "Ana", None, [("ana@x.com", Decimal("50")), ("ana2@x.com", Decimal("50"))]
    )
    registrar_venta(almacen, cid, "2026-03-02", Decimal("10.00"))

    assert ingresos_por_colaborador(almacen, "ana@x.com") == {"2026-03": Decimal("5.00")}
    assert ingresos_por_colaborador(almacen, "ana2@x.com") == {"2026-03": Decimal("5.00")}
