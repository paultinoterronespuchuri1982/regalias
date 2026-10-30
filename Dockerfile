# Imagen de Regalías: solo biblioteca estándar de Python, sin dependencias de runtime.
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 regalias \
    && mkdir -p /data \
    && chown regalias:regalias /data

WORKDIR /app
COPY regalias/ /app/regalias/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER regalias
VOLUME ["/data"]
EXPOSE 8765

# Dentro del contenedor escucha en todas las interfaces, por eso exige REGALIAS_CLAVE.
# Publícalo solo en tu máquina: docker run -p 127.0.0.1:8765:8765 ...
CMD ["python", "-m", "regalias.web", "--db", "/data/regalias.sqlite", "--host", "0.0.0.0", "--puerto", "8765"]
