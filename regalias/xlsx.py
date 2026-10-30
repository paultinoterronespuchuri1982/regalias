"""Generador mínimo de hojas de cálculo .xlsx con la biblioteca estándar.

Un .xlsx es un archivo zip con XML. Solo se usan celdas de texto (inlineStr)
y números; no hay fórmulas, estilos ni hojas múltiples, que es lo que este
proyecto necesita para exportar reportes.
"""

import io
import zipfile
from decimal import Decimal
from typing import Union

Celda = Union[str, int, float, Decimal]

_CONTENIDO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""

_RAIZ = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_LIBRO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Reporte" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""

_RELACIONES_LIBRO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""


def _columna(indice: int) -> str:
    letras = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _escapar(texto: str) -> str:
    """Escapa texto para XML. Solo se escribe XML aquí; no se lee nada."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _celda(referencia: str, valor: Celda) -> str:
    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        return f'<c r="{referencia}"><v>{valor}</v></c>'
    texto = _escapar(str(valor))
    return f'<c r="{referencia}" t="inlineStr"><is><t>{texto}</t></is></c>'


def generar_xlsx(filas: list[list[Celda]]) -> bytes:
    """Devuelve el contenido de un .xlsx con una sola hoja y las filas dadas."""
    filas_xml = []
    for numero, fila in enumerate(filas, start=1):
        celdas = "".join(_celda(f"{_columna(i)}{numero}", valor) for i, valor in enumerate(fila))
        filas_xml.append(f'<row r="{numero}">{celdas}</row>')
    hoja = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(filas_xml)}</sheetData></worksheet>"
    )

    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zip_xlsx:
        zip_xlsx.writestr("[Content_Types].xml", _CONTENIDO)
        zip_xlsx.writestr("_rels/.rels", _RAIZ)
        zip_xlsx.writestr("xl/workbook.xml", _LIBRO)
        zip_xlsx.writestr("xl/_rels/workbook.xml.rels", _RELACIONES_LIBRO)
        zip_xlsx.writestr("xl/worksheets/sheet1.xml", hoja)
    return salida.getvalue()
