from decimal import Decimal

import pytest

from regalias.almacen import Almacen
from regalias.registro import (
    ErrorRegistro,
    registrar_cancion,
    registrar_persona,
    registrar_reproducciones,
    registrar_venta,
)
from regalias.reportes import ingresos_por_colaborador, total_cancion

COLABORADORES = [
    ("ana@x.com", Decimal("50")),
    ("beto@x.com", Decimal("30.5")),
    ("cami@x.com", Decimal("19.5")),
]


@pytest.fixture
def almacen():
    with Almacen(":memory:") as a:
        registrar_persona(a, "ana@x.com", "Ana")
        registrar_persona(a, "beto@x.com", "Beto")
        registrar_persona(a, "cami@x.com", "Cami")
        yield a


def test_registrar_cancion_guarda_datos_y_normaliza_isrc(almacen):
    cid = registrar_cancion(almacen, "Sol", "Ana", "US-RC1-76-07839", COLABORADORES)

    cancion = almacen.obtener_cancion(cid)
    assert cancion["titulo"] == "Sol"
    assert cancion["isrc"] == "USRC17607839"
    assert cancion["colaboradores"] == COLABORADORES


def test_cancion_con_porcentajes_que_no_suman_100_no_se_guarda(almacen):
    with pytest.raises(ErrorRegistro, match="100"):
        registrar_cancion(
            almacen,
            "Sol",
            "Ana",
            None,
            [("ana@x.com", Decimal("60")), ("beto@x.com", Decimal("39.99"))],
        )
    assert almacen.listar_canciones() == []


def test_colaborador_no_registrado_se_rechaza(almacen):
    with pytest.raises(ErrorRegistro, match="no registrado"):
        registrar_cancion(almacen, "Sol", "Ana", None, [("zoe@x.com", Decimal("100"))])


def test_persona_duplicada_por_identificador_se_rechaza(almacen):
    with pytest.raises(ErrorRegistro, match="ya existe"):
        registrar_persona(almacen, "ANA@x.com ", "Otra Ana")


def test_reproducciones_reparten_el_monto_exacto(almacen):
    cid = registrar_cancion(almacen, "Sol", "Ana", None, COLABORADORES)

    monto = registrar_reproducciones(
        almacen, cid, "2026-03-10", cantidad=1000, tarifa=Decimal("0.0037")
    )

    assert monto == Decimal("3.70")
    # 370 centavos: Ana 185, Beto 112 + 1 sobrante (residuo mayor), Cami 72.
    assert total_cancion(almacen, cid) == Decimal("3.70")
    assert ingresos_por_colaborador(almacen, "beto@x.com") == {"2026-03": Decimal("1.13")}


def test_venta_reparte_el_precio_neto_completo(almacen):
    cid = registrar_cancion(almacen, "Sol", "Ana", None, COLABORADORES)

    registrar_venta(almacen, cid, "2026-03-02", Decimal("100.00"))

    assert total_cancion(almacen, cid) == Decimal("100.00")
    assert ingresos_por_colaborador(almacen, "ana@x.com") == {"2026-03": Decimal("50.00")}
    assert ingresos_por_colaborador(almacen, "cami@x.com") == {"2026-03": Decimal("19.50")}


def test_venta_con_precio_negativo_se_rechaza(almacen):
    cid = registrar_cancion(almacen, "Sol", "Ana", None, COLABORADORES)

    with pytest.raises(ValueError):
        registrar_venta(almacen, cid, "2026-03-02", Decimal("-1"))
    assert total_cancion(almacen, cid) == Decimal("0.00")


def test_reproduccion_con_cantidad_negativa_se_rechaza(almacen):
    cid = registrar_cancion(almacen, "Sol", "Ana", None, COLABORADORES)

    with pytest.raises(ValueError):
        registrar_reproducciones(
            almacen, cid, "2026-03-10", cantidad=-5, tarifa=Decimal("0.01")
        )


def test_tarifa_flotante_se_rechaza_para_no_perder_exactitud(almacen):
    cid = registrar_cancion(almacen, "Sol", "Ana", None, COLABORADORES)

    with pytest.raises(TypeError):
        registrar_reproducciones(almacen, cid, "2026-03-10", cantidad=10, tarifa=0.0037)


def test_reporte_agrupa_ingresos_por_periodo(almacen):
    cid = registrar_cancion(almacen, "Sol", "Ana", None, COLABORADORES)
    registrar_venta(almacen, cid, "2026-03-02", Decimal("100.00"))
    registrar_venta(almacen, cid, "2026-04-15", Decimal("40.00"))

    assert ingresos_por_colaborador(almacen, "ana@x.com") == {
        "2026-03": Decimal("50.00"),
        "2026-04": Decimal("20.00"),
    }


def test_suma_de_colaboradores_iguala_total_de_cancion(almacen):
    cid = registrar_cancion(almacen, "Sol", "Ana", None, COLABORADORES)
    registrar_reproducciones(
        almacen, cid, "2026-03-10", cantidad=1000, tarifa=Decimal("0.0037")
    )
    registrar_venta(almacen, cid, "2026-03-12", Decimal("9.99"))

    por_colaborador = sum(
        sum(ingresos_por_colaborador(almacen, identificador).values(), Decimal("0"))
        for identificador, _ in COLABORADORES
    )
    assert por_colaborador == total_cancion(almacen, cid)


def test_evento_de_cancion_inexistente_no_deja_registros(almacen):
    with pytest.raises(ErrorRegistro, match="no existe"):
        registrar_venta(almacen, 999, "2026-03-02", Decimal("10.00"))
    assert almacen.listar_canciones() == []
