# ──────────────────────────────────────────────────
# Stage 1 — build dependencies
# ──────────────────────────────────────────────────
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

# ──────────────────────────────────────────────────
# Stage 2 — runtime
# ──────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        default-libmysqlclient-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Non-root user — added to root group so it can access /var/run/docker.sock
# (docker socket on Docker Desktop is owned root:root 660)
RUN groupadd -r django && useradd -r -g django -d /app -s /sbin/nologin django && \
    usermod -aG root django

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY manage.py .
COPY config/ config/
COPY apps/ apps/
COPY templates/ templates/
COPY docker/entrypoint.sh /entrypoint.sh

# Own everything to django user and ensure apps/ is writable (for chatbot code generation)
RUN mkdir -p /app/staticfiles && \
    chmod +x /entrypoint.sh && \
    chown -R django:django /app /entrypoint.sh && \
    chmod -R u+w /app/apps

USER django

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
