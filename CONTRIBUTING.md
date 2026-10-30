# Cómo contribuir

Gracias por tu interés. Antes de empezar, lee el [README](README.md) para entender
las reglas de negocio y la arquitectura.

## Preparar el entorno

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
```

## Antes de abrir un pull request

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/bandit -q -r regalias
.venv/bin/python -m pytest -o addopts="" -q
```

Si cambias una regla de negocio, escribe primero la prueba que la describe y verifica
que falla antes de implementar el cambio.

## Criterios

- **Dinero:** nunca uses `float`. Los montos van en `Decimal` y en centavos.
- **Dependencias:** la aplicación no debe requerir paquetes de terceros en tiempo de ejecución.
  Las herramientas de desarrollo van en `requirements-dev.txt`.
- **Seguridad:** toda entrada externa se valida. Las consultas SQL usan parámetros.
- **Interfaz:** el texto de la base de datos se escapa antes de mostrarlo. No se usan
  atributos `style` ni scripts en línea, porque la política de contenido los bloquea.
- **Estilo:** el código sigue el formato de `ruff format` y los comentarios explican el porqué,
  no el qué.

## Mensajes de commit

Escribe el asunto en imperativo y en menos de 72 caracteres, por ejemplo
`Corrige el reparto cuando hay centavos sobrantes`.
