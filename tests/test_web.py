import json
import threading
import urllib.error
import urllib.request

import pytest

from regalias.web import crear_servidor


@pytest.fixture
def base(tmp_path):
    servidor = crear_servidor(str(tmp_path / "regalias.sqlite"), puerto=0)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()
    servidor.almacen.cerrar()


def pedir(url, metodo="GET", datos=None, texto=None, tipo_texto="text/plain", cabeceras=None):
    """Devuelve (código, cabeceras, cuerpo) sin lanzar excepciones por códigos de error."""
    if datos is not None:
        cuerpo = json.dumps(datos).encode("utf-8")
    else:
        cuerpo = texto
    peticion = urllib.request.Request(url, data=cuerpo, method=metodo)
    if datos is not None:
        peticion.add_header("Content-Type", "application/json")
    if texto is not None:
        peticion.add_header("Content-Type", tipo_texto)
    for nombre, valor in (cabeceras or {}).items():
        peticion.add_header(nombre, valor)
    try:
        with urllib.request.urlopen(peticion) as respuesta:
            return respuesta.status, dict(respuesta.headers), respuesta.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def cargar_datos_de_ejemplo(base):
    pedir(f"{base}/api/personas", "POST", {"id": "ana@x.com", "nombre": "Ana"})
    pedir(f"{base}/api/personas", "POST", {"id": "beto@x.com", "nombre": "Beto"})
    pedir(f"{base}/api/canciones", "POST", {
        "titulo": "Sol", "artista": "Ana", "isrc": "US-RC1-76-07839",
        "colaboradores": [{"id": "ana@x.com", "pct": "50"}, {"id": "beto@x.com", "pct": "50"}],
    })
    pedir(f"{base}/api/eventos", "POST", {
        "cancionId": 1, "tipo": "reproduccion", "fecha": "2026-03-10",
        "cantidad": 1000, "tarifa": "0.0037",
    })


def test_flujo_completo_por_api(base):
    cargar_datos_de_ejemplo(base)

    codigo, _, cuerpo = pedir(f"{base}/api/reporte?persona=beto@x.com")
    reporte = json.loads(cuerpo)

    assert codigo == 200
    assert reporte["periodos"] == [{"periodo": "2026-03", "monto": "1.85"}]
    assert reporte["total"] == "1.85"


def test_canciones_y_eventos_se_listan_con_montos(base):
    cargar_datos_de_ejemplo(base)

    _, _, cuerpo = pedir(f"{base}/api/canciones")
    canciones = json.loads(cuerpo)
    _, _, cuerpo = pedir(f"{base}/api/eventos")
    eventos = json.loads(cuerpo)

    assert canciones[0]["titulo"] == "Sol"
    assert canciones[0]["total"] == "3.70"
    assert eventos[0]["monto"] == "3.70"
    assert {r["nombre"]: r["monto"] for r in eventos[0]["reparto"]} == {"Ana": "1.85", "Beto": "1.85"}


def test_porcentajes_invalidos_devuelven_400_con_mensaje(base):
    pedir(f"{base}/api/personas", "POST", {"id": "ana@x.com", "nombre": "Ana"})
    pedir(f"{base}/api/personas", "POST", {"id": "beto@x.com", "nombre": "Beto"})

    codigo, _, cuerpo = pedir(f"{base}/api/canciones", "POST", {
        "titulo": "Sol", "artista": "Ana", "isrc": None,
        "colaboradores": [{"id": "ana@x.com", "pct": "60"}, {"id": "beto@x.com", "pct": "39.99"}],
    })

    assert codigo == 400
    assert "100" in json.loads(cuerpo)["error"]


def test_colaborador_no_registrado_devuelve_400(base):
    codigo, _, cuerpo = pedir(f"{base}/api/canciones", "POST", {
        "titulo": "Sol", "artista": "Ana", "isrc": None,
        "colaboradores": [{"id": "zoe@x.com", "pct": "100"}],
    })

    assert codigo == 400
    assert "no registrado" in json.loads(cuerpo)["error"]


def test_tipo_de_contenido_incorrecto_devuelve_415(base):
    codigo, _, _ = pedir(f"{base}/api/personas", "POST", texto=b"id=ana")

    assert codigo == 415


def test_json_invalido_devuelve_400(base):
    codigo, _, _ = pedir(f"{base}/api/personas", "POST", texto=b"{no es json",
                         tipo_texto="application/json")

    assert codigo == 400


def test_cuerpo_demasiado_grande_devuelve_413(base):
    codigo, _, _ = pedir(f"{base}/api/personas", "POST", {"id": "x" * 70_000, "nombre": "Ana"})

    assert codigo == 413


def test_host_ajeno_se_rechaza(base):
    codigo, _, _ = pedir(f"{base}/api/personas", cabeceras={"Host": "evil.example"})

    assert codigo == 403


def test_pagina_principal_lleva_cabeceras_de_seguridad(base):
    codigo, cabeceras, cuerpo = pedir(f"{base}/")

    assert codigo == 200
    assert "default-src 'self'" in cabeceras["Content-Security-Policy"]
    assert cabeceras["X-Frame-Options"] == "DENY"
    assert cabeceras["X-Content-Type-Options"] == "nosniff"
    assert b"<title>" in cuerpo


def test_reporte_csv_se_descarga(base):
    cargar_datos_de_ejemplo(base)

    codigo, cabeceras, cuerpo = pedir(f"{base}/api/reporte.csv?persona=beto@x.com")

    assert codigo == 200
    assert cabeceras["Content-Type"].startswith("text/csv")
    assert cuerpo.decode("utf-8").splitlines() == ["periodo,monto", "2026-03,1.85", "total,1.85"]


def test_persona_inexistente_en_reporte_devuelve_404(base):
    codigo, _, _ = pedir(f"{base}/api/reporte?persona=nadie@x.com")

    assert codigo == 404


def test_ruta_inexistente_devuelve_404(base):
    codigo, _, _ = pedir(f"{base}/api/no-existe")

    assert codigo == 404
