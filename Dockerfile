# ─────────────────────────────────────────────────────────────────────────────
#  SIG Platform — Dockerfile (versión distribuible)
#
#  Este Dockerfile está pensado para que el DESARROLLADOR construya
#  la imagen y la publique. El usuario final sólo necesita la imagen.
#
#  Construir y exportar:
#    docker build -t sig-platform:test .
#    docker save sig-platform:test | gzip > sig-platform-test.tar.gz
#
#  o subir a un registry privado:
#    docker tag sig-platform:test <registry>/sig-platform:test
#    docker push <registry>/sig-platform:test
#
#  El usuario final carga la imagen así:
#    docker load -i sig-platform-test.tar.gz
#  y luego ejecuta:
#    python app.py
#
#  Contexto de build requerido (debe ejecutarse desde la raíz del repo):
#    docker build -f Dockerfile .
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: dependencias ─────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        default-libmysqlclient-dev \
        pkg-config && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements/ requirements/
RUN pip install --no-cache-dir --prefix=/install -r requirements/production.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        default-libmysqlclient-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Usuario no-root con acceso al socket de Docker
RUN groupadd -r django && useradd -r -g django -d /app -s /sbin/nologin django && \
    usermod -aG root django

WORKDIR /app

# Dependencias desde el stage de build
COPY --from=builder /install /usr/local

# Código de la aplicación
COPY manage.py .
COPY config/ config/
COPY apps/ apps/
COPY templates/ templates/

# Entrypoint embebido (sin depender de docker/entrypoint.sh)
RUN printf '#!/bin/sh\nset -eu\necho "==> Running migrations..."\npython manage.py migrate --noinput\necho "==> Collecting static files..."\npython manage.py collectstatic --noinput\nexec "$@"\n' \
    > /entrypoint.sh && chmod +x /entrypoint.sh

RUN mkdir -p /app/staticfiles /app/media && \
    chown -R django:django /app /entrypoint.sh && \
    chmod -R u+w /app/apps

USER django

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.asgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--timeout", "0", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
