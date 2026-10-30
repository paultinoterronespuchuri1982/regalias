# Regalías

Herramienta de línea de comandos para que artistas independientes registren
canciones, colaboradores e ingresos (reproducciones y ventas), y calculen cuánto
le corresponde a cada persona según el porcentaje acordado.

- Python 3.9 o superior, sin dependencias en tiempo de ejecución.
- Almacenamiento local en SQLite. No hay servicios externos.
- Todo el dinero se calcula con `Decimal` y en centavos enteros. No se usan flotantes.

## Instalación

```bash
git clone https://github.com/paultinoterronespuchuri1982/regalias.git
cd regalias
python3 -m venv .venv
.venv/bin/pip install pytest
```

## Uso

Todos los comandos aceptan `--db` para elegir el archivo SQLite (por defecto `regalias.sqlite`).

```bash
# 1. Registrar a cada persona con un identificador único (correo o código)
.venv/bin/python -m regalias.cli persona --id ana@x.com --nombre Ana
.venv/bin/python -m regalias.cli persona --id beto@x.com --nombre Beto

# 2. Registrar una canción. Los porcentajes deben sumar exactamente 100.
.venv/bin/python -m regalias.cli cancion --titulo Sol --artista Ana \
    --isrc US-RC1-76-07839 --colaborador ana@x.com:50 --colaborador beto@x.com:50

# 3. Registrar ingresos
.venv/bin/python -m regalias.cli reproducciones --cancion 1 --fecha 2026-03-10 --cantidad 1000 --tarifa 0.0037
.venv/bin/python -m regalias.cli venta --cancion 1 --fecha 2026-04-02 --precio 10.00

# 4. Ver el reporte de una persona, agrupado por mes
.venv/bin/python -m regalias.cli reporte --colaborador beto@x.com
```

Los errores de negocio salen con código 1 y un mensaje explicando qué corregir.

## Interfaz web

```bash
.venv/bin/python -m regalias.web --db regalias.sqlite
```

Abre http://127.0.0.1:8765 en tu navegador. Desde ahí puedes registrar personas,
canciones e ingresos, ver los reportes por mes y descargar el reporte de una persona
en CSV. Usa el mismo archivo SQLite que la línea de comandos.

El servidor usa solo la biblioteca estándar de Python y escucha únicamente en
`127.0.0.1`, así que no es accesible desde otras computadoras.

## Reglas de negocio

- **Porcentajes:** entre 0 y 100, con máximo dos decimales, y la suma debe ser exactamente 100.
- **Identificadores:** no distinguen mayúsculas ni espacios sobrantes. `ANA@x.com ` y `ana@x.com` son la misma persona. No se puede registrar dos veces.
- **ISRC:** opcional. Se normaliza (sin guiones, en mayúsculas) y debe tener el formato estándar. No se puede repetir.
- **Montos:** dos decimales, redondeo mitad hacia arriba. Las tarifas pueden tener hasta seis decimales.
- **Reparto:** cada evento se reparte al registrarse. Cada persona recibe la parte entera en centavos. El centavo sobrante va a quien tenga el mayor residuo; en empate, al colaborador registrado primero. Así la suma de lo repartido es siempre igual al monto del evento.
- **Valores no válidos:** no se aceptan negativos, `NaN`, `Infinity` ni flotantes.

## Arquitectura

```
regalias/
  dinero.py     Aritmética monetaria: conversión segura a Decimal y reparto exacto
  registro.py   Reglas de negocio: personas, canciones, ISRC, eventos
  almacen.py    Persistencia en SQLite; cada evento y su reparto se guardan en una transacción
  reportes.py   Consultas: ingresos por persona y período, total por canción
  cli.py        Interfaz de línea de comandos (argparse)
tests/          Pruebas con pytest, una por regla de negocio
```

Flujo de un ingreso:

1. `cli.py` recibe los datos y los pasa a `registro.py`.
2. `registro.py` valida (formato de fecha, montos, existencia de la canción) y calcula el monto.
3. `dinero.py` reparte el monto entre los colaboradores con la regla exacta de centavos.
4. `almacen.py` guarda el evento y su reparto en una sola transacción. Si algo falla, no queda nada a medias.
5. `reportes.py` suma los repartos por persona y período cuando se pide un reporte.

La capa de datos no decide reglas de negocio: `almacen.py` solo guarda y consulta.

## Pruebas

```bash
.venv/bin/python -m pytest -q
```

Las pruebas cubren las reglas de porcentajes, redondeo, reparto exacto, rechazo de valores no válidos, transacciones, reportes y la CLI de punta a punta.

## Seguridad

- Todas las consultas SQL usan parámetros; no hay concatenación de texto en SQL.
- `bandit` no reporta hallazgos sobre el código del paquete.
- El servidor web escucha solo en `127.0.0.1` y rechaza peticiones cuyo `Host` no sea local, lo que protege contra ataques de DNS rebinding desde una página ajena.
- Las escrituras exigen `Content-Type: application/json` y tienen un límite de 64 KB.
- Las respuestas incluyen una Content-Security-Policy estricta (sin scripts ni estilos en línea de otros orígenes), `X-Frame-Options: DENY` y `nosniff`.
- Los errores internos devuelven un mensaje genérico; el detalle solo aparece en la consola del servidor.
- La interfaz muestra el texto escapado; no se inserta HTML proveniente de los datos.
- La base de datos es un archivo local sin cifrar. Quien tenga acceso al archivo tiene acceso a los datos.
- No hay autenticación: el programa confía en quien lo ejecuta en su computadora.
- No está pensado para usarse como servicio web. Si algún día se expone en red, necesitará autenticación y control de acceso.

## Limitaciones

- Una persona se identifica por su identificador. Si la misma persona tiene dos identificadores (por ejemplo, dos correos), aparecerá separada.
- La exportación es a CSV. No hay PDF ni Excel.
- El servidor web no tiene usuarios ni contraseñas: cualquiera con acceso a tu sesión local puede usarlo.
- Las bases de datos creadas antes de agregar identificadores de persona no son compatibles; hay que volver a crearlas.
