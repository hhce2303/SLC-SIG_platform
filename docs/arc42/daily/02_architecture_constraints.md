# 2. Restricciones de Arquitectura — Módulo `daily`

## 2.1 Restricciones técnicas

| Restricción | Detalle |
|---|---|
| Stack | Django ≥5.1, DRF ≥3.15, `djangorestframework-simplejwt` ≥5.3, Python. `requirements/base.txt` fija estas versiones para toda la plataforma — no solo para `daily`. |
| Base de datos | MySQL (`sig_dailylogs`, alias `default`). Producción corre temporalmente sobre **MariaDB 10.11** (GoDaddy), pero el target real y documentado es **MySQL 8.0** — hay planes de revertir. Ninguna migración de este módulo puede usar tipos/sintaxis nativos de MariaDB. Antecedente ya conocido: `apps/installations/migrations/0008_mariadb_uuid_and_pending_state.py` usa el tipo `uuid` nativo de MariaDB y **romperá** cuando producción vuelva a MySQL (documentado en `docs/LOCAL_MIRROR.md`). |
| Modelo de usuario | `AUTH_USER_MODEL` no está customizado — es el `django.contrib.auth.User` de stock. Cualquier esquema de auth nuevo (como el de [ADR-0001](decisions/0001-jwt-desacoplado-de-usuarios-django.md)) debe convivir con esto, no reemplazarlo a nivel de framework. |
| Firma JWT | Un solo `SECRET_KEY` firma **todos** los JWT de la plataforma (daily, platform, y cualquier otro consumidor de `rest_framework_simplejwt`). No hay aislamiento criptográfico por módulo — el aislamiento es por forma del claim únicamente. |
| Múltiples DBs | La plataforma mantiene 4 alias de base de datos (`default`=sig_dailylogs, `inventory`, `schedules`, `sigtools`=sigtools_beta en GoDaddy 72.167.56.142) enrutados vía `DATABASE_ROUTERS` (`config/db_router.py`). `daily`/`users`/`platform` viven todos en `default`. |
| Estilo DRF de la plataforma | `APIView` únicamente — **no** `ModelViewSet` ni `DefaultRouter` en ningún módulo de esta plataforma (confirmado por grep repo-wide). Capas: `views.py` (orquestación HTTP delgada) → `serializers.py` (validación) → `services.py` (escrituras) / `selectors.py` (lecturas, a menudo SQL crudo vía `connections[alias].cursor()` contra esquemas legacy). `@extend_schema` de `drf_spectacular` para OpenAPI. |
| Caché/tiempo real | Redis compartido (`django_redis`, prefijo de key `dlb`) para caché de lookups (`daily_user:<pk>`, TTL 60s) y pub/sub para los streams SSE existentes (`GET /api/v1/inventory/stream/`, `/installations/stream/`). |

## 2.2 Restricciones organizacionales

| Restricción | Detalle |
|---|---|
| Ramas y PRs | Skill `git-control`: `feature/*` → PR → `main`. En la práctica **no existe una rama `develop`** pese a que el skill la documenta — todo se mergea directo a `main` (discrepancia ya señalada en [11_risks_and_technical_debt.md](11_risks_and_technical_debt.md)). |
| Cambios de base de datos | Checklist obligatorio antes de tocar producción: backup (`scripts/backup_db.py`) → probar en local `mysql:8.0` (nunca MariaDB) → documentar el cambio → autorización del project lead → aplicar y verificar. |
| Despliegue | MKS (producción) es despliegue **manual, sin CI** — requiere sincronizar git antes de reconstruir la imagen, o el código queda stale en silencio. Ver `docs/DEPLOYMENT.md` y el skill `docker-django-ops`. |
| Documentación de dominio | Convención de idioma español para docs de dominio/negocio (`README.md`, `docs/Front/*`); inglés reservado para docs puramente operacionales (`DEPLOYMENT.md`, skills). Este espacio arc42 sigue la convención de dominio: español. |

## 2.3 Convenciones ya establecidas que este módulo hereda

- Serializers de lectura/escritura separados (`*ReadSerializer` / `*WriteSerializer`) cuando el endpoint está respaldado por SQL crudo.
- Excepciones de servicio tipadas (`apps.core.exceptions.ServiceException`, `ResourceNotFound`, `ConflictError`) en vez de excepciones genéricas.
- FKs hacia tablas legacy `managed=False` usan `db_constraint=False` — no se le pide a Django que gestione una constraint de integridad referencial que no controla del todo.
