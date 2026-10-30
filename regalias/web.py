"""Servidor web local: API JSON y la interfaz de regalias/static.

Seguridad:
- Escucha solo en 127.0.0.1; no es accesible desde otras computadoras.
- Acepta solo peticiones cuyo encabezado Host sea local (protege contra DNS rebinding).
- Las escrituras requieren Content-Type application/json y tienen tamaño máximo.
- Cabeceras que impiden cargar scripts ajenos, incrustar la página y filtrar referencias.
- Los errores devuelven un mensaje; los detalles técnicos solo van a la consola del servidor.
"""

import argparse
import csv
import hmac
import io
import json
import os
import sys
import traceback
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from regalias.almacen import Almacen
from regalias.registro import (
    ErrorRegistro,
    clave_colaborador,
    registrar_cancion,
    registrar_persona,
    registrar_reproducciones,
    registrar_venta,
)
from regalias.reportes import ingresos_por_colaborador, total_cancion
from regalias.xlsx import generar_xlsx

ESTATICO = Path(__file__).parent / "static"
ARCHIVOS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
}
LIMITE_CUERPO = 64 * 1024
HOSTS_PERMITIDOS = {"127.0.0.1", "localhost"}
HOSTS_LOCALES = {"127.0.0.1", "localhost", "::1"}
CABECERAS_SEGURIDAD = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class PeticionInvalida(Exception):
    """Petición rechazada, con el código HTTP que debe devolverse."""

    def __init__(self, codigo: int, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def _texto(datos: dict, campo: str) -> str:
    valor = datos.get(campo)
    if not isinstance(valor, str):
        raise PeticionInvalida(400, f"'{campo}' debe ser texto.")
    return valor


def _texto_opcional(datos: dict, campo: str) -> Optional[str]:
    valor = datos.get(campo)
    if valor is None or valor == "":
        return None
    if not isinstance(valor, str):
        raise PeticionInvalida(400, f"'{campo}' debe ser texto.")
    return valor


def _entero(datos: dict, campo: str) -> int:
    valor = datos.get(campo)
    if not isinstance(valor, int) or isinstance(valor, bool):
        raise PeticionInvalida(400, f"'{campo}' debe ser un número entero.")
    return valor


def _decimal(texto: str, campo: str) -> Decimal:
    try:
        return Decimal(texto)
    except InvalidOperation:
        raise ErrorRegistro(f"'{campo}' no es un número válido: {texto!r}.") from None


def dinero(valor: Decimal) -> str:
    """Formatea un monto con dos decimales."""
    return f"{valor:.2f}"


def listar_personas(almacen: Almacen) -> list[dict[str, str]]:
    """Personas para la API: identificador y nombre."""
    return [
        {"id": identificador, "nombre": nombre}
        for _, identificador, nombre in almacen.listar_personas()
    ]


def listar_canciones(almacen: Almacen) -> list[dict[str, object]]:
    """Canciones con sus colaboradores y su total."""
    canciones = []
    for cancion_id in almacen.listar_canciones():
        cancion = almacen.obtener_cancion(cancion_id)
        colaboradores = []
        for clave, pct in cancion["colaboradores"]:
            identificador, nombre = almacen.obtener_persona(clave)
            colaboradores.append({"id": identificador, "nombre": nombre, "pct": f"{pct:.2f}"})
        canciones.append(
            {
                "id": cancion_id,
                "titulo": cancion["titulo"],
                "artista": cancion["artista"],
                "isrc": cancion["isrc"],
                "colaboradores": colaboradores,
                "total": dinero(total_cancion(almacen, cancion_id)),
            }
        )
    return canciones


def listar_eventos(almacen: Almacen) -> list[dict[str, object]]:
    """Eventos con tipo, fecha, monto y reparto."""
    titulos = {c["id"]: c["titulo"] for c in listar_canciones(almacen)}
    return [
        {
            "id": e["id"],
            "cancion": titulos.get(e["cancion_id"], ""),
            "tipo": e["tipo"],
            "fecha": e["fecha"],
            "monto": dinero(e["monto"]),
            "reparto": [{"nombre": r["nombre"], "monto": dinero(r["monto"])} for r in e["reparto"]],
        }
        for e in almacen.listar_eventos()
    ]


def reporte_persona(almacen: Almacen, identificador: str) -> dict[str, object]:
    """Ingresos de una persona por mes. Lanza 404 si no existe."""
    clave = clave_colaborador(identificador)
    persona = almacen.obtener_persona(clave)
    if persona is None:
        raise PeticionInvalida(404, "Persona no encontrada.")
    periodos = ingresos_por_colaborador(almacen, identificador)
    return {
        "id": persona[0],
        "nombre": persona[1],
        "periodos": [{"periodo": p, "monto": dinero(m)} for p, m in periodos.items()],
        "total": dinero(sum(periodos.values(), Decimal("0.00"))),
    }


def reporte_csv(almacen: Almacen, identificador: str) -> str:
    """Reporte de una persona como texto CSV."""
    reporte = reporte_persona(almacen, identificador)
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["periodo", "monto"])
    for fila in reporte["periodos"]:
        escritor.writerow([fila["periodo"], fila["monto"]])
    escritor.writerow(["total", reporte["total"]])
    return salida.getvalue()


class Manejador(BaseHTTPRequestHandler):
    """Atiende las peticiones HTTP: archivos estáticos y la API JSON."""

    server_version = "Regalias"
    sys_version = ""

    def log_message(self, formato, *args) -> None:
        """Silencia el registro de cada petición en la consola."""
        return  # Sin registro de accesos en la consola.

    def do_GET(self) -> None:
        """Atiende una petición GET."""
        self._atender("GET")

    def do_POST(self) -> None:
        """Atiende una petición POST."""
        self._atender("POST")

    def _atender(self, metodo: str) -> None:
        try:
            if not self._host_permitido():
                return self._enviar_json(403, {"error": "Host no permitido."})
            ruta = urlparse(self.path)
            if metodo == "GET" and ruta.path in ARCHIVOS:
                return self._enviar_archivo(ruta.path)
            if ruta.path.startswith("/api/"):
                if not self._clave_valida():
                    return self._enviar_json(
                        401,
                        {"error": "Clave requerida o incorrecta."},
                        {"WWW-Authenticate": "Bearer"},
                    )
                return self._api(metodo, ruta)
            raise PeticionInvalida(404, "No existe esa ruta.")
        except PeticionInvalida as error:
            self._enviar_json(error.codigo, {"error": str(error)})
        except (ValueError, TypeError) as error:
            self._enviar_json(400, {"error": str(error)})
        except Exception:
            traceback.print_exc(file=sys.stderr)
            self._enviar_json(500, {"error": "Error interno. Revisa la consola del servidor."})

    def _api(self, metodo: str, ruta) -> None:
        almacen = self.server.almacen
        consulta = parse_qs(ruta.query)
        clave = (metodo, ruta.path)

        if clave == ("GET", "/api/personas"):
            return self._enviar_json(200, listar_personas(almacen))
        if clave == ("POST", "/api/personas"):
            datos = self._leer_cuerpo()
            registrar_persona(almacen, _texto(datos, "id"), _texto(datos, "nombre"))
            return self._enviar_json(201, {"ok": True})

        if clave == ("GET", "/api/canciones"):
            return self._enviar_json(200, listar_canciones(almacen))
        if clave == ("POST", "/api/canciones"):
            datos = self._leer_cuerpo()
            colaboradores = datos.get("colaboradores")
            if not isinstance(colaboradores, list):
                raise PeticionInvalida(400, "'colaboradores' debe ser una lista.")
            pares = []
            for colaborador in colaboradores:
                if not isinstance(colaborador, dict):
                    raise PeticionInvalida(400, "Cada colaborador debe ser un objeto.")
                pares.append(
                    (_texto(colaborador, "id"), _decimal(_texto(colaborador, "pct"), "pct"))
                )
            cancion_id = registrar_cancion(
                almacen,
                _texto(datos, "titulo"),
                _texto(datos, "artista"),
                _texto_opcional(datos, "isrc"),
                pares,
            )
            return self._enviar_json(201, {"id": cancion_id})

        if clave == ("GET", "/api/eventos"):
            return self._enviar_json(200, listar_eventos(almacen))
        if clave == ("POST", "/api/eventos"):
            datos = self._leer_cuerpo()
            cancion_id = _entero(datos, "cancionId")
            tipo = _texto(datos, "tipo")
            fecha = _texto(datos, "fecha")
            if tipo == "reproduccion":
                monto = registrar_reproducciones(
                    almacen, cancion_id, fecha, _entero(datos, "cantidad"), _texto(datos, "tarifa")
                )
            elif tipo == "venta":
                monto = registrar_venta(almacen, cancion_id, fecha, _texto(datos, "precio"))
            else:
                raise PeticionInvalida(400, "'tipo' debe ser 'reproduccion' o 'venta'.")
            return self._enviar_json(201, {"monto": dinero(monto)})

        if clave == ("GET", "/api/reporte"):
            return self._enviar_json(
                200, reporte_persona(almacen, self._persona_consulta(consulta))
            )
        if clave == ("GET", "/api/reporte.csv"):
            texto = reporte_csv(almacen, self._persona_consulta(consulta))
            return self._enviar(
                200,
                texto.encode("utf-8"),
                "text/csv; charset=utf-8",
                {"Content-Disposition": 'attachment; filename="reporte.csv"'},
            )
        if clave == ("GET", "/api/reporte.xlsx"):
            reporte = reporte_persona(almacen, self._persona_consulta(consulta))
            filas = [["Mes", "Ingresos"]]
            filas += [[p["periodo"], float(p["monto"])] for p in reporte["periodos"]]
            filas.append(["Total", float(reporte["total"])])
            return self._enviar(
                200,
                generar_xlsx(filas),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                {"Content-Disposition": 'attachment; filename="reporte.xlsx"'},
            )

        raise PeticionInvalida(404, "No existe esa ruta.")

    def _persona_consulta(self, consulta: dict) -> str:
        valores = consulta.get("persona", [""])
        if not valores[0].strip():
            raise PeticionInvalida(400, "Falta el parámetro 'persona'.")
        return valores[0]

    def _clave_valida(self) -> bool:
        """Sin clave configurada, la API está abierta (solo en 127.0.0.1)."""
        clave = self.server.clave
        if not clave:
            return True
        encabezado = self.headers.get("Authorization", "")
        recibida = encabezado[len("Bearer ") :] if encabezado.startswith("Bearer ") else ""
        return hmac.compare_digest(recibida.encode("utf-8"), clave.encode("utf-8"))

    def _host_permitido(self) -> bool:
        host = self.headers.get("Host", "")
        nombre = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
        return nombre in HOSTS_PERMITIDOS

    def _leer_cuerpo(self) -> dict:
        tipo = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if tipo != "application/json":
            raise PeticionInvalida(415, "Se espera Content-Type: application/json.")
        try:
            largo = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise PeticionInvalida(400, "Content-Length inválido.") from None
        if largo < 0 or largo > LIMITE_CUERPO:
            raise PeticionInvalida(413, "La petición es demasiado grande.")
        crudo = self.rfile.read(largo)
        try:
            datos = json.loads(crudo.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PeticionInvalida(400, "JSON inválido.") from None
        if not isinstance(datos, dict):
            raise PeticionInvalida(400, "Se espera un objeto JSON.")
        return datos

    def _enviar_archivo(self, ruta: str) -> None:
        nombre, tipo = ARCHIVOS[ruta]
        self._enviar(200, (ESTATICO / nombre).read_bytes(), tipo)

    def _enviar_json(self, codigo: int, datos, extra: Optional[dict[str, str]] = None) -> None:
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self._enviar(codigo, cuerpo, "application/json; charset=utf-8", extra)

    def _enviar(
        self, codigo: int, cuerpo: bytes, tipo: str, extra: Optional[dict[str, str]] = None
    ) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        for nombre, valor in {**CABECERAS_SEGURIDAD, **(extra or {})}.items():
            self.send_header(nombre, valor)
        self.end_headers()
        self.wfile.write(cuerpo)


def crear_servidor(
    ruta_db: str, puerto: int = 8765, clave: Optional[str] = None, host: str = "127.0.0.1"
) -> HTTPServer:
    """Crea el servidor. Fuera de localhost exige clave."""
    if host not in HOSTS_LOCALES and not clave:
        raise ValueError(
            "Para escuchar fuera de 127.0.0.1 hay que definir una clave (--clave o REGALIAS_CLAVE)."
        )
    servidor = HTTPServer((host, puerto), Manejador)
    servidor.almacen = Almacen(ruta_db)
    servidor.clave = clave or None
    return servidor


def main(argv: Optional[list[str]] = None) -> int:
    """Arranca el servidor desde la línea de comandos."""
    parser = argparse.ArgumentParser(prog="regalias-web")
    parser.add_argument("--db", default="regalias.sqlite", help="archivo SQLite")
    parser.add_argument("--puerto", type=int, default=8765)
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="dirección de escucha; usa 0.0.0.0 solo con clave (p. ej. en Docker)",
    )
    parser.add_argument(
        "--clave",
        default=os.environ.get("REGALIAS_CLAVE"),
        help="clave para usar la API (también puede ir en REGALIAS_CLAVE)",
    )
    args = parser.parse_args(argv)

    try:
        servidor = crear_servidor(args.db, args.puerto, args.clave, args.host)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if args.clave:
        print("Clave requerida: ingrésala en la página para usar la aplicación.")
    print(f"Regalías en http://{args.host}:{args.puerto}  (Ctrl+C para detener)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
        servidor.almacen.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
