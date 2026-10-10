# Contrato del borde (nginx compartido)

Documento de la **Fase 0** de la extracción del borde a un repo de infraestructura compartida
(informe: `SIG-SLC/reports/Extraer nginx a servicios compartidos.md`). Describe lo que existe hoy; no
cambia comportamiento. Cuando el borde se mueva a su propio repo, este contrato viaja con él.

## Topología actual

```
cliente ──► SIGplatform-nginx ──┬─ api.sig.systems  (y server_name "_") ──► web:8000  (Django, este repo)
            (nginx:alpine)      └─ desk.sig.systems /desk-api/*  ──► sigdesk-kong:8000  (Kong, SIG-Desk-Backend)
```

- Imagen `nginx:alpine`, contenedor `SIGplatform-nginx`, sin Dockerfile propio.
- Puerto de host: `${NGINX_PORT:-8091}` → 80 del contenedor (`docker/docker-compose.yml`). 443 solo con el overlay `docker-compose.ssl.yml` (certificado autofirmado local).
- Config: `docker/nginx.conf/default.conf` (api) y `ssl.conf` (solo espejo local). El vhost de SIG-Desk va **inline** en `docker/docker-compose.sigdesk.yml` (bloque `configs`).

## Red `sig-edge`

| Aspecto | Valor |
|---|---|
| Nombre | `sig-edge` (red bridge externa) |
| Creación | A mano, una vez: `docker network create sig-edge`. **Hoy no tiene dueño.** |
| Miembros | `SIGplatform-nginx` (overlay `docker-compose.sigdesk.yml`) y `kong` de SIG-Desk (`SIG-Desk-Backend/compose.edge.yaml`) |
| Alias estable de Kong | `sigdesk-kong` (puerto 8000) |
| Resolución | nginx resuelve `sigdesk-kong` por petición (`resolver 127.0.0.11` + variable), así que arranca aunque Kong esté caído; Kong caído = 502 solo en `desk.sig.systems` |

Solo funciona con ambos stacks **en el mismo host Docker**.

## Vhosts

| Host | Ruta | Destino | Notas |
|---|---|---|---|
| `api.sig.systems` / `_` | `/api/` | `web:8000` | SSE: buffering off, `proxy_read_timeout 86400`, `Connection ""` |
| | `/web-auth/` | `web:8000` | proxy estándar |
| | `/media/` | `alias /app/media/` (volumen `media_data`, solo lectura) | cache 7 d |
| `desk.sig.systems` | `/desk-api/*` | `sigdesk-kong:8000` sin el prefijo | `proxy_read_timeout 86400`; `/` devuelve 404 |

- `client_max_body_size 50M` en ambos (planos indoor en SLC).
- nginx envía `Host`, `X-Real-IP`, `X-Forwarded-For` y `X-Forwarded-Proto`.
- No hay en nginx: CORS, rate limit, headers de seguridad, gzip. CORS/CSRF/HSTS los maneja Django (SLC) y el plugin `cors` de Kong (SIG-Desk, `kong.yml`).
- Timeouts a tener en cuenta: nginx 86400 s vs Kong 60 s por defecto (120 s en el advisor de IA).

## Quién es dueño de qué

| Pieza | Dueño hoy | Dueño objetivo (Fase 2) |
|---|---|---|
| Servicio nginx, certificados, red `sig-edge` | SLC-SIG_platform | repo de infraestructura compartida |
| Vhost `api.sig.systems` | SLC | SLC (archivo propio en `conf.d/`) |
| Vhost `desk.sig.systems` | SLC (inline en el overlay) | SIG-Desk (archivo propio en `conf.d/`) |
| Políticas de API (auth, CORS, rutas de servicio) | Kong, SIG-Desk-Backend | igual |
| Aprobación de cambios de ruta | **sin definir** | CODEOWNERS por consumidor |

## Ajustes de Django detrás del proxy

- `TRUST_PROXY_HEADERS` (env, `false` por defecto): si es `true` activa `SECURE_PROXY_SSL_HEADER` y `USE_X_FORWARDED_HOST`. Activarlo cuando el borde termine TLS; mientras tanto no cambia nada.
- `ALLOWED_HOSTS`: el código sigue teniendo `*` como default; los despliegues deben fijarlo por entorno (ver `.env.example`).
- `SIGTOOLS_COOKIE_DOMAIN` (`.sig.systems`) depende del dominio público del borde.
- SIG-Desk autentica contra SIGTools en `api.sig.systems:8091`: cambiar ese host o puerto lo rompe.

## Validación

`.github/workflows/nginx-validate.yml` corre `nginx -t` (default.conf, ssl.conf y default.conf + vhost de SIG-Desk) en cada PR que toque la config del borde. No despliega.

## Decisiones confirmadas (2026-10-09)

1. **SIG-Desk correrá en producción** (MKS). El overlay `sigdesk` aún no está en CI/deploy de producción: pendiente de la Fase 1/2.
2. **Certificados: gestión manual** (sin renovación automática por ahora). Automatizar queda para la Fase 3.
3. **Dueño del borde y aprobador de cambios de ruta: Héctor Cruz.**

## Preguntas abiertas

1. ¿En qué componente termina TLS en producción (nginx del borde, según el plan)? Falta confirmarlo al activar HTTPS.
2. ¿Puerto real por entorno: 8091 (default de compose) u 80 (como dicen algunos docs)?
