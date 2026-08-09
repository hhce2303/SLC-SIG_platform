# 7. Vista de Despliegue — Módulo `daily`

`daily` no tiene topología de despliegue propia — corre dentro del mismo contenedor/proceso Django que el resto de la plataforma. Ver [docs/DEPLOYMENT.md](../../DEPLOYMENT.md) (arquitectura de despliegue completa) y el skill `docker-django-ops` para el protocolo operativo Docker+Django+MySQL.

## 7.1 Topología observada (mirror local)

El stack Docker corriendo en esta máquina (`docker/docker-compose*.yml`) expone:

| Contenedor | Imagen | Rol |
|---|---|---|
| `SIGplatform-web` | build propio (Django + gunicorn) | Sirve la API, incluye `apps.daily` tras esta sesión. |
| `SIGplatform-nginx` | `nginx:alpine` | Reverse proxy, puertos 80/443. |
| `SIGplatform-mirror-db` | `mariadb:10.11` | Mirror local de producción — MariaDB, no MySQL (ver restricción en [02_architecture_constraints.md](02_architecture_constraints.md)). |
| `SIGplatform-redis` | `redis:7-alpine` | Caché + pub/sub SSE. |
| `SIGplatform-poller` | build propio | Proceso worker aparte (poller), no expone puerto HTTP. |

Importante: el contenedor `web` **no monta el código como volumen** — la imagen se construye una vez con el código copiado adentro. Cambios en disco (como los de esta sesión) no se reflejan automáticamente; hace falta `docker cp` + reiniciar, o una rebuild completa, para que un despliegue real los tome.

## 7.2 Verificación de esta sesión

La corrección del rename `apps.reports`→`apps.daily` se verificó copiando los archivos cambiados (`apps/daily/*`, `config/settings/base.py`, `config/urls.py`) al contenedor `SIGplatform-web` vía `docker cp` y corriendo `python manage.py check` dentro del contenedor — pasó sin errores (`System check identified no issues (0 silenced)`), confirmando que `apps.daily` registra correctamente y que el URL conf resuelve. Esto fue una verificación puntual, no un despliegue — el próximo build de imagen debe tomar los archivos ya corregidos en disco de forma natural.

## 7.3 Restricción de motor de base de datos

El mirror local corre MariaDB 10.11 porque así corre producción **hoy**, pero el objetivo documentado es volver a MySQL 8.0. Cualquier migración nueva de este módulo (ej. la de `UserToolAccess.user` en `apps/platform`, ver ADR-0001) debe probarse contra `mysql:8.0` local — no basta con que pase en el mirror MariaDB — precisamente por el antecedente ya conocido en `apps/installations/migrations/0008_mariadb_uuid_and_pending_state.py`.
