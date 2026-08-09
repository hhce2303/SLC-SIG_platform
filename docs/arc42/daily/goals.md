# 1. Introducción y Objetivos — Módulo `daily`

> Sección 1 del template [arc42](https://arc42.org/) para el dominio **Daily Log** (operadores de centro de monitoreo, estaciones, sesiones, eventos, despacho policial). Este es el único módulo de la plataforma SLC-SIG que documenta su arquitectura en formato arc42; el resto sigue usando el esquema plano de `docs/`.

## 1.1 Requisitos esenciales

- **Reemplazar Supabase por un backend propio.** El dominio "Daily Log" corre hoy en producción sobre **Supabase** (Postgres + Auth + RPCs `SECURITY DEFINER` + Realtime + 1 edge function), consumido por el frontend **SIGDailyReport** (repo aparte, `Documents\GitHub\SIGDailyReport`). El mismo dominio (`daily_users`, `daily_events`, `daily_sites`, `daily_activities`, `daily_covers_*`...) ya existe, parcialmente, como base MySQL legacy (`sig_dailylogs`) dentro de esta plataforma (SLC-SIG platform).
- **Django como orquestador propio.** En vez de depender de un BaaS de terceros, esta plataforma (`apps/daily`, `apps/users`, y los módulos que se sumen conforme avancemos) pasa a ser el backend de referencia del dominio daily: autenticación, reglas de negocio, acceso a datos y tiempo real quedan orquestados por Django, no por Supabase.
- **Incremental, no big-bang.** Este objetivo se persigue en fases. La primera fase (esta) resuelve únicamente el contrato de autenticación (JWT) y deja la documentación arquitectónica en marcha; el mapeo completo de las ~60 tablas y RPCs de Supabase a endpoints DRF es trabajo futuro, documentado a medida que se aborde (ver [ADR-0002](decisions/0002-django-como-orquestador-reemplazo-supabase.md)).

## 1.2 Metas de calidad

Ranking de prioridades para este módulo, de mayor a menor:

| # | Meta de calidad | Motivación |
|---|---|---|
| 1 | **Continuidad operativa** | Los operadores de centro de monitoreo trabajan turnos largos y no pueden permitirse un cierre de sesión forzado a mitad de turno. El contrato JWT (ver [ADR-0001](decisions/0001-jwt-desacoplado-de-usuarios-django.md)) prioriza esto explícitamente sobre la rotación estricta de tokens. |
| 2 | **Un solo backend por dominio** | Ya existía un segundo intento de backend Django para este mismo dominio, abandonado sin usar (ver [ADR-0003](decisions/0003-abandono-scaffold-daily-log-backend.md)). No se repite ese error: `apps/daily` + `apps/users` son la única fuente de verdad del lado Django. |
| 3 | **Consistencia con el resto de la plataforma** | Mismo estilo DRF (`APIView` + `selectors`/`services`, sin routers), mismas reglas de seguridad de base de datos (backup + prueba local en `mysql:8.0` antes de tocar producción), mismo esquema de autenticación multi-scheme ya usado por `apps/sigtools_auth`. |

## 1.3 Stakeholders

| Rol | Interés |
|---|---|
| Operadores / Supervisores / Admins (Daily Log) | Usar el sistema sin interrupciones de sesión; no notar el cambio de backend. |
| Equipo de desarrollo SIG | Un solo backend Django que mantener para este dominio; migraciones seguras. |
| SIGDailyReport (frontend, futuro consumidor) | Punto de integración a mediano plazo — hoy solo referencia de dominio, sin cambios de código todavía. |

## 1.4 Alcance de esta fase / No-objetivos

- **No se toca código de SIGDailyReport todavía.** Se usa exclusivamente como referencia para entender el dominio (tablas, RPCs, flujo de auth actual). La migración real del frontend (apuntar a la nueva API Django en vez de Supabase) queda para una fase futura, a documentar cuando se aborde.
- **No se revive** el scaffold Django/DRF paralelo `SIGDailyReport/daily-log-backend/` (abandonado, ver ADR-0003).
- Esta fase resuelve el **contrato de autenticación** (JWT desacoplado de `django.contrib.auth.User`) y dos consumidores confirmados (`apps/users`, `apps/platform`). No incluye todavía el mapeo de endpoints de negocio del dominio Supabase.

---

Índice completo de la documentación arc42 de este módulo: ver [09_architecture_decisions.md](09_architecture_decisions.md) para la bitácora de decisiones, y el resto de las secciones numeradas en esta misma carpeta.
