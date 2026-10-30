"""Aritmética monetaria con Decimal y reparto exacto en centavos."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Dict, List, Tuple

CENTAVO = Decimal("0.01")
CIEN = Decimal("100")


def _decimal(valor: object, nombre: str) -> Decimal:
    """Convierte a Decimal finito. Rechaza flotantes, NaN, Infinity y texto inválido."""
    if isinstance(valor, float):
        raise TypeError(f"Use Decimal o str para {nombre}, no float.")
    if not isinstance(valor, (Decimal, int, str)):
        raise TypeError(f"Tipo no soportado para {nombre}: {type(valor).__name__}")
    try:
        numero = Decimal(valor)
    except InvalidOperation:
        raise ValueError(f"{nombre.capitalize()} inválido: {valor!r}.")
    if not numero.is_finite():
        raise ValueError(f"{nombre.capitalize()} debe ser un número finito.")
    return numero


def a_dinero(valor: object) -> Decimal:
    """Convierte un monto a Decimal con dos decimales. Rechaza flotantes y negativos."""
    numero = _decimal(valor, "monto")
    try:
        monto = numero.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError("El monto es demasiado grande.")
    if monto < 0:
        raise ValueError("El monto no puede ser negativo.")
    return monto


def a_tasa(valor: object) -> Decimal:
    """Convierte una tarifa (p. ej. por reproducción) a Decimal sin redondear."""
    tarifa = _decimal(valor, "tarifa")
    if tarifa < 0:
        raise ValueError("La tarifa no puede ser negativa.")
    return tarifa


def repartir(total: Decimal, partes: List[Tuple[str, Decimal]]) -> Dict[str, Decimal]:
    """Reparte `total` según porcentajes, con la suma exacta igual al total.

    Cada parte recibe la porción entera en centavos (redondeo hacia abajo).
    Los centavos sobrantes van a las partes con mayor residuo; en empate,
    gana la parte que aparece primero en `partes`.
    """
    if total < 0:
        raise ValueError("El total a repartir no puede ser negativo.")
    if total != total.quantize(CENTAVO):
        raise ValueError("El total a repartir debe tener como máximo dos decimales.")
    suma = sum((pct for _, pct in partes), Decimal("0"))
    if suma != CIEN:
        raise ValueError(f"Los porcentajes deben sumar 100; suman {suma}.")

    centavos_total = int(total / CENTAVO)
    exactos = [(clave, centavos_total * pct / CIEN) for clave, pct in partes]
    base = [(clave, int(exacto)) for clave, exacto in exactos]
    sobrante = centavos_total - sum(cent for _, cent in base)

    orden = sorted(
        range(len(exactos)),
        key=lambda i: (-(exactos[i][1] - base[i][1]), i),
    )
    extra = {i: 0 for i in range(len(exactos))}
    for i in orden[:sobrante]:
        extra[i] = 1

    return {
        clave: (base[i][1] + extra[i]) * CENTAVO
        for i, (clave, _) in enumerate(exactos)
    }
