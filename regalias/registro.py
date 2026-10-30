"""Reglas de negocio para el registro de personas, canciones y eventos."""

import datetime
import re
from decimal import Decimal
from typing import List, Optional, Tuple

from regalias.dinero import CENTAVO, a_dinero, a_tasa, repartir


class ErrorRegistro(ValueError):
    """Se lanza cuando un dato viola una regla de negocio."""


_ISRC_PATRON = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}\d{2}\d{5}$")


def _limpiar(texto: str, campo: str) -> str:
    """Quita espacios sobrantes y colapsa los internos. Rechaza textos vacíos."""
    limpio = " ".join(texto.split())
    if not limpio:
        raise ErrorRegistro(f"{campo.capitalize()} no puede estar vacío.")
    return limpio


def clave_colaborador(identificador: str) -> str:
    """Clave de identidad de una persona: sin espacios extra ni distinción de mayúsculas."""
    return _limpiar(identificador, "el identificador").casefold()


def validar_porcentajes(colaboradores: List[Tuple[str, Decimal]]) -> None:
    """Exige porcentajes finitos entre 0 y 100, con máximo dos decimales, que sumen exactamente 100."""
    for nombre, pct in colaboradores:
        if not pct.is_finite():
            raise ErrorRegistro(f"El porcentaje de '{nombre}' no es un número válido.")
        if pct < 0 or pct > 100:
            raise ErrorRegistro(f"El porcentaje de '{nombre}' debe estar entre 0 y 100.")
        if pct != pct.quantize(CENTAVO):
            raise ErrorRegistro(
                f"El porcentaje de '{nombre}' admite como máximo dos decimales."
            )
    suma = sum((pct for _, pct in colaboradores), Decimal("0"))
    if suma != Decimal("100"):
        raise ErrorRegistro(
            f"Los porcentajes deben sumar exactamente 100; suman {suma}."
        )


def normalizar_isrc(isrc: Optional[str]) -> Optional[str]:
    """Quita guiones, pasa a mayúsculas y valida el formato ISRC. None es válido (opcional)."""
    if isrc is None:
        return None
    limpio = isrc.replace("-", "").upper()
    if not _ISRC_PATRON.match(limpio):
        raise ErrorRegistro(f"ISRC inválido: '{isrc}'.")
    return limpio


def registrar_persona(almacen, identificador: str, nombre: str) -> None:
    """Registra una persona con un identificador único (correo, código, etc.)."""
    identificador_limpio = _limpiar(identificador, "el identificador")
    clave = clave_colaborador(identificador)
    if almacen.obtener_persona(clave) is not None:
        raise ErrorRegistro(f"La persona '{identificador_limpio}' ya existe.")
    almacen.crear_persona(clave, identificador_limpio, _limpiar(nombre, "el nombre"))


def registrar_cancion(
    almacen,
    titulo: str,
    artista: str,
    isrc: Optional[str],
    colaboradores: List[Tuple[str, Decimal]],
) -> int:
    """Valida y guarda una canción. Los colaboradores se identifican por su identificador."""
    if not titulo.strip() or not artista.strip():
        raise ErrorRegistro("Título y artista principal son obligatorios.")
    claves = [clave_colaborador(identificador) for identificador, _ in colaboradores]
    if len(claves) != len(set(claves)):
        raise ErrorRegistro("Los colaboradores de una canción no pueden repetirse.")
    validar_porcentajes(
        [(_limpiar(identificador, "el identificador"), pct) for identificador, pct in colaboradores]
    )
    isrc_normalizado = normalizar_isrc(isrc)
    if isrc_normalizado is not None and almacen.existe_isrc(isrc_normalizado):
        raise ErrorRegistro(f"El ISRC {isrc_normalizado} ya está registrado.")

    filas = []
    for clave, (_, pct) in zip(claves, colaboradores):
        persona = almacen.obtener_persona(clave)
        if persona is None:
            raise ErrorRegistro(
                f"Colaborador no registrado: '{clave}'. Regístralo primero con persona."
            )
        filas.append((clave, persona[1], pct))
    return almacen.crear_cancion(
        titulo.strip(), artista.strip(), isrc_normalizado, filas
    )


def registrar_reproducciones(
    almacen,
    cancion_id: int,
    fecha: str,
    cantidad: int,
    tarifa: Decimal,
) -> Decimal:
    """Registra reproducciones (cantidad × tarifa por reproducción) y su reparto."""
    if cantidad < 0:
        raise ErrorRegistro("La cantidad de reproducciones no puede ser negativa.")
    tarifa = a_tasa(tarifa)
    monto = a_dinero(Decimal(cantidad) * tarifa)
    _guardar(almacen, cancion_id, "reproduccion", fecha, cantidad, tarifa, monto)
    return monto


def registrar_venta(almacen, cancion_id: int, fecha: str, precio_neto: Decimal) -> Decimal:
    """Registra una venta por su precio neto y su reparto."""
    monto = a_dinero(precio_neto)
    _guardar(almacen, cancion_id, "venta", fecha, 1, monto, monto)
    return monto


def _guardar(almacen, cancion_id, tipo, fecha, cantidad, tarifa, monto) -> None:
    datetime.date.fromisoformat(fecha)  # Lanza ValueError si la fecha no es AAAA-MM-DD.
    cancion = almacen.obtener_cancion(cancion_id)
    if cancion is None:
        raise ErrorRegistro(f"La canción {cancion_id} no existe.")
    reparto = repartir(monto, cancion["colaboradores"])
    almacen.guardar_evento(cancion_id, tipo, fecha, cantidad, tarifa, monto, reparto)
