# 8. Conceptos Transversales — Módulo `daily`

## 8.1 Autenticación (resuelto)

JWT desacoplado de `django.contrib.auth.User` — ver [ADR-0001](decisions/0001-jwt-desacoplado-de-usuarios-django.md) para el diseño completo. Resumen: `DailyJWTAuthentication` (BaseAuthentication) + `DailyJWTUser` (wrapper liviano) + `DailyAccessToken` (subclase de `AccessToken`, vida ~10 años, sin refresh token), calcado del patrón `SigtoolsCookieAuthentication`/`SigtoolsWebUser` de `apps/sigtools_auth`.

## 8.2 Acceso a datos legacy

Todo el dominio daily vive en tablas legacy de `sig_dailylogs`, la mayoría accedidas de dos formas:

- **Modelos `managed=False`** (`apps.core.models`) cuando se necesita el ORM (filtros, `select_related`, transacciones) — usado para `User`, `UserRole`, `UserName`, `StationMap`, `Session`.
- **SQL crudo vía `connections["default"].cursor()`** cuando la consulta es de agregación/reporte y no amerita un modelo (`apps/daily/selectors.py`).

Ninguna migración de Django gestiona el *schema* de estas tablas (son `managed=False`) — las migraciones de esta plataforma solo tocan tablas nuevas propias (ej. la futura migración de `UserToolAccess.user` en `apps/platform`).

## 8.3 Manejo de errores

Excepciones de servicio tipadas en `apps.core.exceptions`: `ServiceException` (400, error de validación/credenciales), `ResourceNotFound` (404), `ConflictError` (409 — ej. estación ocupada). Las vistas no atrapan excepciones genéricas de Python; dejan que estas propaguen y las traduce el manejador de excepciones de DRF.

## 8.4 Caché

Redis compartido (`django_redis`, prefijo `dlb`), TTL por defecto 5 min salvo que se especifique. Patrón de cache-aside usado tanto por `DailyUserMiddleware` como por `DailyJWTAuthentication`: `cache_key = f"daily_user:{pk}"`, TTL 60s — deliberadamente el mismo formato de key entre ambos, para que cualquiera de los dos que corra primero en un request caliente la entrada para el otro.

## 8.5 Documentación de API

`drf-spectacular` genera el esquema OpenAPI (`/api/schema/`, `/api/docs/`, `/api/redoc/`). Cada vista anota sus respuestas con `@extend_schema`. La descripción global de autenticación (`SPECTACULAR_SETTINGS["DESCRIPTION"]` en `config/settings/base.py`) debe actualizarse cuando se implemente ADR-0001, porque hoy describe el flujo viejo (access 60 min + refresh 7 días con rotación) que deja de ser cierto para `daily`/`platform`.

## 8.6 Internacionalización de la documentación

Este módulo documenta en español (dominio de negocio), siguiendo la convención ya usada en `README.md` y `docs/Front/*`. El código en sí (nombres de clases, docstrings) permanece en inglés, como el resto de la plataforma.
