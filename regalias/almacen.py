"""Almacenamiento local en SQLite. Los montos se guardan como texto para conservar Decimal."""

import sqlite3
from decimal import Decimal
from types import TracebackType
from typing import Optional

ESQUEMA = """
CREATE TABLE IF NOT EXISTS personas (
    clave           TEXT PRIMARY KEY,
    identificador   TEXT NOT NULL,
    nombre          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS canciones (
    id      INTEGER PRIMARY KEY,
    titulo  TEXT NOT NULL,
    artista TEXT NOT NULL,
    isrc    TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS colaboradores (
    id          INTEGER PRIMARY KEY,
    cancion_id  INTEGER NOT NULL REFERENCES canciones(id),
    clave       TEXT NOT NULL REFERENCES personas(clave),
    nombre      TEXT NOT NULL,
    porcentaje  TEXT NOT NULL CHECK (CAST(porcentaje AS REAL) >= 0),
    orden       INTEGER NOT NULL,
    UNIQUE (cancion_id, clave)
);
CREATE TABLE IF NOT EXISTS eventos (
    id          INTEGER PRIMARY KEY,
    cancion_id  INTEGER NOT NULL REFERENCES canciones(id),
    tipo        TEXT NOT NULL CHECK (tipo IN ('reproduccion', 'venta')),
    fecha       TEXT NOT NULL,
    cantidad    INTEGER NOT NULL CHECK (cantidad >= 0),
    tarifa      TEXT NOT NULL,
    monto       TEXT NOT NULL CHECK (CAST(monto AS REAL) >= 0)
);
CREATE TABLE IF NOT EXISTS repartos (
    evento_id       INTEGER NOT NULL REFERENCES eventos(id),
    colaborador_id  INTEGER NOT NULL REFERENCES colaboradores(id),
    monto           TEXT NOT NULL,
    PRIMARY KEY (evento_id, colaborador_id)
);
"""


class Almacen:
    """Acceso a la base de datos SQLite. Cada escritura es una transacción."""

    def __init__(self, ruta: str) -> None:
        # El servidor local atiende una petición a la vez, así que una sola conexión basta.
        self._conn = sqlite3.connect(ruta, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(ESQUEMA)

    def __enter__(self) -> "Almacen":
        return self

    def __exit__(
        self,
        tipo: Optional[type[BaseException]],
        valor: Optional[BaseException],
        traza: Optional[TracebackType],
    ) -> None:
        self.cerrar()

    def cerrar(self) -> None:
        """Cierra la conexión con la base de datos."""
        self._conn.close()

    def crear_persona(self, clave: str, identificador: str, nombre: str) -> None:
        """Guarda una persona. La clave es su identificador en minúsculas."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO personas (clave, identificador, nombre) VALUES (?, ?, ?)",
                (clave, identificador, nombre),
            )

    def obtener_persona(self, clave: str) -> Optional[tuple[str, str]]:
        """Devuelve (identificador, nombre) de la persona, o None si no existe."""
        fila = self._conn.execute(
            "SELECT identificador, nombre FROM personas WHERE clave = ?", (clave,)
        ).fetchone()
        return None if fila is None else (fila[0], fila[1])

    def crear_cancion(
        self,
        titulo: str,
        artista: str,
        isrc: Optional[str],
        colaboradores: list[tuple[str, str, Decimal]],
    ) -> int:
        """Guarda la canción. `colaboradores` trae (clave, nombre, porcentaje)."""
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO canciones (titulo, artista, isrc) VALUES (?, ?, ?)",
                (titulo, artista, isrc),
            )
            cancion_id = cursor.lastrowid
            self._conn.executemany(
                "INSERT INTO colaboradores (cancion_id, clave, nombre, porcentaje, orden)"
                " VALUES (?, ?, ?, ?, ?)",
                [
                    (cancion_id, clave, nombre, str(pct), orden)
                    for orden, (clave, nombre, pct) in enumerate(colaboradores)
                ],
            )
        return cancion_id

    def existe_isrc(self, isrc: str) -> bool:
        """Indica si ya hay una canción con ese ISRC normalizado."""
        return (
            self._conn.execute("SELECT 1 FROM canciones WHERE isrc = ?", (isrc,)).fetchone()
            is not None
        )

    def obtener_cancion(self, cancion_id: int) -> Optional[dict[str, object]]:
        """Devuelve título, artista, ISRC y colaboradores (clave, porcentaje), o None."""
        fila = self._conn.execute(
            "SELECT titulo, artista, isrc FROM canciones WHERE id = ?", (cancion_id,)
        ).fetchone()
        if fila is None:
            return None
        filas = self._conn.execute(
            "SELECT clave, porcentaje FROM colaboradores WHERE cancion_id = ? ORDER BY orden",
            (cancion_id,),
        ).fetchall()
        return {
            "titulo": fila[0],
            "artista": fila[1],
            "isrc": fila[2],
            "colaboradores": [(clave, Decimal(pct)) for clave, pct in filas],
        }

    def listar_canciones(self) -> list[int]:
        """Devuelve los ids de todas las canciones."""
        return [fila[0] for fila in self._conn.execute("SELECT id FROM canciones ORDER BY id")]

    def guardar_evento(
        self,
        cancion_id: int,
        tipo: str,
        fecha: str,
        cantidad: int,
        tarifa: Decimal,
        monto: Decimal,
        reparto: dict[str, Decimal],
    ) -> int:
        """Guarda el evento y su reparto (por clave de persona) en una sola transacción."""
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO eventos (cancion_id, tipo, fecha, cantidad, tarifa, monto)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (cancion_id, tipo, fecha, cantidad, str(tarifa), str(monto)),
            )
            evento_id = cursor.lastrowid
            ids = dict(
                self._conn.execute(
                    "SELECT clave, id FROM colaboradores WHERE cancion_id = ?",
                    (cancion_id,),
                ).fetchall()
            )
            self._conn.executemany(
                "INSERT INTO repartos (evento_id, colaborador_id, monto) VALUES (?, ?, ?)",
                [(evento_id, ids[clave], str(parte)) for clave, parte in reparto.items()],
            )
        return evento_id

    def listar_personas(self) -> list[tuple[str, str, str]]:
        """Devuelve (clave, identificador, nombre) de cada persona."""
        return [
            tuple(fila)
            for fila in self._conn.execute(
                "SELECT clave, identificador, nombre FROM personas ORDER BY nombre, identificador"
            )
        ]

    def listar_eventos(self) -> list[dict[str, object]]:
        """Devuelve los eventos con su reparto por colaborador."""
        eventos = [
            {
                "id": fila[0],
                "cancion_id": fila[1],
                "tipo": fila[2],
                "fecha": fila[3],
                "monto": Decimal(fila[4]),
                "reparto": [],
            }
            for fila in self._conn.execute(
                "SELECT id, cancion_id, tipo, fecha, monto FROM eventos ORDER BY id"
            )
        ]
        indice = {evento["id"]: evento for evento in eventos}
        for evento_id, clave, nombre, monto in self._conn.execute(
            "SELECT r.evento_id, c.clave, c.nombre, r.monto FROM repartos r"
            " JOIN colaboradores c ON c.id = r.colaborador_id"
            " ORDER BY r.evento_id, c.orden"
        ):
            indice[evento_id]["reparto"].append(
                {"clave": clave, "nombre": nombre, "monto": Decimal(monto)}
            )
        return eventos

    def montos_de_cancion(self, cancion_id: int) -> list[Decimal]:
        """Devuelve el monto de cada evento de una canción."""
        return [
            Decimal(fila[0])
            for fila in self._conn.execute(
                "SELECT monto FROM eventos WHERE cancion_id = ?", (cancion_id,)
            )
        ]

    def repartos_de_colaborador(self, clave: str) -> list[tuple[str, Decimal]]:
        """Devuelve (fecha, monto) de cada reparto de la persona con esa clave."""
        return [
            (fecha, Decimal(monto))
            for fecha, monto in self._conn.execute(
                "SELECT e.fecha, r.monto FROM repartos r"
                " JOIN colaboradores c ON c.id = r.colaborador_id"
                " JOIN eventos e ON e.id = r.evento_id"
                " WHERE c.clave = ?",
                (clave,),
            )
        ]
