from decimal import Decimal

import pytest

from regalias.dinero import a_dinero, repartir


def test_a_dinero_redondea_a_dos_decimales_con_mitad_hacia_arriba():
    assert a_dinero("10.005") == Decimal("10.01")
    assert a_dinero("1.234") == Decimal("1.23")


def test_a_dinero_acepta_enteros_y_decimales():
    assert a_dinero(5) == Decimal("5.00")
    assert a_dinero(Decimal("2.5")) == Decimal("2.50")


def test_a_dinero_rechaza_flotantes():
    with pytest.raises(TypeError):
        a_dinero(0.1)


def test_a_dinero_rechaza_negativos():
    with pytest.raises(ValueError):
        a_dinero("-0.01")


def test_repartir_mitades_exactas():
    resultado = repartir(Decimal("100.00"), [("a", Decimal("50")), ("b", Decimal("50"))])
    assert resultado == {"a": Decimal("50.00"), "b": Decimal("50.00")}


def test_repartir_asigna_centavo_sobrante_al_mayor_residuo_y_luego_al_primero():
    # 10.00 entre tres partes iguales: 33.33 cada una, sobra 1 centavo.
    partes = [("a", Decimal("33.34")), ("b", Decimal("33.33")), ("c", Decimal("33.33"))]
    resultado = repartir(Decimal("10.00"), partes)
    assert resultado == {
        "a": Decimal("3.34"),
        "b": Decimal("3.33"),
        "c": Decimal("3.33"),
    }


def test_repartir_empate_de_residuos_se_resuelve_por_orden():
    # 0.05 con 70/30: exactos 3.5 y 1.5 centavos; ambos residuos son 0.5.
    # El primero gana el centavo sobrante.
    resultado = repartir(Decimal("0.05"), [("a", Decimal("70")), ("b", Decimal("30"))])
    assert resultado == {"a": Decimal("0.04"), "b": Decimal("0.01")}


def test_repartir_siempre_iguala_el_total():
    total = Decimal("0.03")
    partes = [("a", Decimal("33.33")), ("b", Decimal("33.33")), ("c", Decimal("33.34"))]
    assert sum(repartir(total, partes).values()) == total


def test_repartir_total_cero_da_ceros():
    resultado = repartir(Decimal("0"), [("a", Decimal("60")), ("b", Decimal("40"))])
    assert resultado == {"a": Decimal("0.00"), "b": Decimal("0.00")}
