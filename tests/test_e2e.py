"""Pruebas de extremo a extremo en un navegador real (Chromium con Playwright).

Se omiten si Playwright o Chromium no están instalados:
    .venv/bin/pip install playwright && .venv/bin/python -m playwright install chromium
"""

import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from regalias.web import crear_servidor  # noqa: E402


@pytest.fixture
def base(tmp_path):
    servidor = crear_servidor(str(tmp_path / "e2e.sqlite"), puerto=0)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()
    servidor.almacen.cerrar()


@pytest.fixture
def navegador():
    with sync_api.sync_playwright() as playwright:
        try:
            navegador = playwright.chromium.launch()
        except Exception as error:  # Chromium no instalado en esta máquina.
            pytest.skip(f"Chromium no disponible: {error}")
        yield navegador
        navegador.close()


def registrar_persona(pagina, identificador, nombre, existentes):
    pagina.click('button[data-tab="personas"]')
    # Espera el contador esperado: la pestaña ya terminó de cargar sus datos.
    pagina.wait_for_selector(f"text=Personas ({existentes})")
    pagina.fill("#p-id", identificador)
    pagina.fill("#p-nombre", nombre)
    pagina.click("#f-persona button[type=submit]")
    pagina.wait_for_selector(f"td:has-text('{identificador}')")


def test_flujo_completo_en_el_navegador(base, navegador):
    pagina = navegador.new_page()
    errores_de_pagina = []
    pagina.on("pageerror", lambda error: errores_de_pagina.append(str(error)))
    pagina.goto(base)
    # Espera a que termine la carga inicial de datos antes de escribir en los formularios.
    pagina.wait_for_selector("text=Personas (0)")

    registrar_persona(pagina, "ana@x.com", "Ana", 0)
    registrar_persona(pagina, "beto@x.com", "Beto", 1)
    registrar_persona(pagina, "cami@x.com", "Cami", 2)

    # Canción: 50 + 30.5 + 19.5 = 100, con el contador de suma en vivo.
    pagina.click('button[data-tab="canciones"]')
    pagina.fill("#c-titulo", "Sol")
    pagina.fill("#c-artista", "Ana")
    pagina.fill("#c-isrc", "US-RC1-76-07839")
    for persona, pct in [("ana@x.com", "50"), ("beto@x.com", "30.5"), ("cami@x.com", "19.5")]:
        pagina.select_option("#c-persona", persona)
        pagina.fill("#c-pct", pct)
        pagina.click("#c-agregar")
    pagina.wait_for_selector("text=Suma: 100.00 / 100")
    pagina.click("#f-cancion button[type=submit]")
    pagina.wait_for_selector("text=Canción registrada.")
    pagina.wait_for_selector("td:has-text('Sol')")

    # Ingresos: una reproducción (3.70) y una venta (10.00).
    pagina.click('button[data-tab="eventos"]')
    pagina.select_option("#e-cancion", label="Sol")
    pagina.fill("#e-cantidad", "1000")
    pagina.fill("#e-tarifa", "0.0037")
    pagina.fill("#e-fecha", "2026-03-10")
    pagina.click("#f-evento button[type=submit]")
    pagina.wait_for_selector("text=Ingreso registrado por 3.70.")

    pagina.select_option("#e-tipo", "venta")
    pagina.fill("#e-precio", "10.00")
    pagina.fill("#e-fecha", "2026-04-02")
    pagina.click("#f-evento button[type=submit]")
    pagina.wait_for_selector("text=Ingreso registrado por 10.00.")

    # Reportes de Beto: marzo 1.13 (30.5 % de 3.70), abril 3.05, total 4.18.
    pagina.click('button[data-tab="reportes"]')
    pagina.select_option("#r-persona", "beto@x.com")
    # Espera el valor de Beto: el reporte de Ana (50 %) también tiene filas de 2026-04.
    pagina.wait_for_selector("td:has-text('1.13')")
    tabla = pagina.inner_text("table")
    assert "2026-03" in tabla and "1.13" in tabla
    assert "2026-04" in tabla and "3.05" in tabla
    assert "4.18" in tabla
    enlace = pagina.get_attribute("a.enlace", "href")
    assert enlace.startswith("/api/reporte.csv?persona=beto%40x.com")

    with pagina.expect_download() as descarga:
        pagina.click("text=Descargar Excel")
    assert descarga.value.suggested_filename == "reporte.xlsx"

    assert errores_de_pagina == []


def test_pide_clave_y_entra_con_la_correcta(tmp_path, navegador):
    servidor = crear_servidor(str(tmp_path / "clave.sqlite"), puerto=0, clave="clave-e2e")
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        pagina = navegador.new_page()
        pagina.goto(f"http://127.0.0.1:{servidor.server_address[1]}")
        pagina.wait_for_selector("text=Clave de acceso")

        pagina.fill("#k-clave", "incorrecta")
        pagina.click("#f-clave button[type=submit]")
        pagina.wait_for_selector("text=Clave incorrecta.")

        pagina.fill("#k-clave", "clave-e2e")
        pagina.click("#f-clave button[type=submit]")
        pagina.wait_for_selector("text=Personas (0)")
    finally:
        servidor.shutdown()
        servidor.server_close()
        servidor.almacen.cerrar()
