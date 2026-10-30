"""Reportes de ingresos por canción y por colaborador."""

from decimal import Decimal

from regalias.almacen import Almacen
from regalias.registro import clave_colaborador


def total_cancion(almacen: Almacen, cancion_id: int) -> Decimal:
    """Suma los ingresos de todos los eventos de una canción."""
    return sum(almacen.montos_de_cancion(cancion_id), Decimal("0.00"))


def ingresos_por_colaborador(almacen: Almacen, identificador: str) -> dict[str, Decimal]:
    """Ingresos de una persona agrupados por período AAAA-MM, en orden cronológico."""
    totales: dict[str, Decimal] = {}
    for fecha, monto in almacen.repartos_de_colaborador(clave_colaborador(identificador)):
        periodo = fecha[:7]
        totales[periodo] = totales.get(periodo, Decimal("0.00")) + monto
    return dict(sorted(totales.items()))
