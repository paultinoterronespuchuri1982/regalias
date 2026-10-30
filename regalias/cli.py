"""Interfaz de línea de comandos mínima para el control de regalías."""

import argparse
import sys
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

from regalias.almacen import Almacen
from regalias.registro import (
    registrar_cancion,
    registrar_persona,
    registrar_reproducciones,
    registrar_venta,
)
from regalias.reportes import ingresos_por_colaborador


def _colaborador(texto: str) -> Tuple[str, Decimal]:
    nombre, separador, pct = texto.rpartition(":")
    if not separador or not nombre:
        raise argparse.ArgumentTypeError("Use NOMBRE:PORCENTAJE")
    try:
        return nombre, Decimal(pct)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"Porcentaje inválido: '{pct}'")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="regalias")
    parser.add_argument("--db", default="regalias.sqlite", help="archivo SQLite")
    comandos = parser.add_subparsers(dest="comando", required=True)

    persona = comandos.add_parser("persona", help="registrar una persona colaboradora")
    persona.add_argument("--id", required=True, help="identificador único (correo, código)")
    persona.add_argument("--nombre", required=True)

    cancion = comandos.add_parser("cancion", help="registrar una canción")
    cancion.add_argument("--titulo", required=True)
    cancion.add_argument("--artista", required=True)
    cancion.add_argument("--isrc")
    cancion.add_argument(
        "--colaborador", action="append", type=_colaborador, required=True,
        help="NOMBRE:PORCENTAJE (repetible)",
    )

    reproducciones = comandos.add_parser("reproducciones", help="registrar reproducciones")
    reproducciones.add_argument("--cancion", type=int, required=True)
    reproducciones.add_argument("--fecha", required=True, help="AAAA-MM-DD")
    reproducciones.add_argument("--cantidad", type=int, required=True)
    reproducciones.add_argument("--tarifa", required=True, help="por reproducción")

    venta = comandos.add_parser("venta", help="registrar una venta")
    venta.add_argument("--cancion", type=int, required=True)
    venta.add_argument("--fecha", required=True, help="AAAA-MM-DD")
    venta.add_argument("--precio", required=True, help="precio neto")

    reporte = comandos.add_parser("reporte", help="ingresos por colaborador")
    reporte.add_argument("--colaborador", required=True)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        with Almacen(args.db) as almacen:
            if args.comando == "persona":
                registrar_persona(almacen, args.id, args.nombre)
                print(f"Persona '{args.id}' registrada.")
            elif args.comando == "cancion":
                cid = registrar_cancion(
                    almacen, args.titulo, args.artista, args.isrc, args.colaborador
                )
                print(f"Canción registrada con id {cid}.")
            elif args.comando == "reproducciones":
                monto = registrar_reproducciones(
                    almacen, args.cancion, args.fecha, args.cantidad, args.tarifa
                )
                print(f"Reproducciones registradas por {monto}.")
            elif args.comando == "venta":
                monto = registrar_venta(
                    almacen, args.cancion, args.fecha, args.precio
                )
                print(f"Venta registrada por {monto}.")
            elif args.comando == "reporte":
                for periodo, monto in ingresos_por_colaborador(
                    almacen, args.colaborador
                ).items():
                    print(f"{periodo}  {monto}")
    except (ValueError, TypeError, InvalidOperation) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
