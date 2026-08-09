# 3. Alcance y Contexto del Sistema — Módulo `daily`

## 3.1 Contexto de negocio

```
                         ┌─────────────────────────────┐
                         │   SIGDailyReport (frontend)  │
                         │   React + TS + Vite          │
                         │   HOY: 100% sobre Supabase   │
                         └──────────────┬───────────────┘
                                        │ (referencia de dominio
                                        │  por ahora — sin integrar)
                                        ▼
        ┌───────────────────────────────────────────────────────┐
        │                 SLC-SIG platform (Django)              │
        │                                                        │
        │   apps/daily ── apps/users ── apps/platform ── apps/core│
        │        │             │              │                  │
        │        └─────────────┴──────────────┴──── DB "default" │
        │                     (sig_dailylogs, MySQL)              │
        └───────────────────────────────────────────────────────┘
                     │                              │
                     ▼                              ▼
        ┌─────────────────────┐         ┌───────────────────────┐
        │  Operadores /        │         │  Herramientas de      │
        │  Supervisores /Admins│         │  plataforma           │
        │  (centro de monitoreo)│        │  (installations.sig.  │
        │                       │        │  systems, inventory.  │
        │                       │        │  sig.systems, etc.)   │
        └─────────────────────┘         └───────────────────────┘
```

## 3.2 Vecinos externos

| Sistema | Relación | Estado |
|---|---|---|
| **SIGDailyReport** (repo aparte, `Documents\GitHub\SIGDailyReport`) | Frontend React+TS+Vite del dominio daily. Hoy corre 100% sobre Supabase: Auth propio + ~60 tablas Postgres (2 proyectos: `daily` y `splits`) + RPCs `SECURITY DEFINER` + Realtime + 1 edge function (`site-connectivity-check`). Es el futuro consumidor de este backend Django. | **Solo referencia** por ahora — ver [ADR-0002](decisions/0002-django-como-orquestador-reemplazo-supabase.md). Sin integración de código todavía. |
| **`SIGDailyReport/daily-log-backend/`** | Backend Django/DRF paralelo, dentro del mismo repo del frontend, apuntando también a `sig_dailylogs`. | **Abandonado** — ver [ADR-0003](decisions/0003-abandono-scaffold-daily-log-backend.md). No es un vecino activo. |
| **sigtools_beta** (MySQL, GoDaddy 72.167.56.142) | Base legacy externa, expuesta de solo lectura vía `apps/sigtools` como proxy de catálogo de sitios. | Activa, usada por otros módulos de la plataforma (installations, inventory), no específica de `daily`. |
| **Redis** | Caché compartida (lookups de `daily_user`) y pub/sub para SSE. | Activa, compartida con toda la plataforma. |
| **Microsoft Graph** | Envío de correo (alertas de artículos dañados, etc.) vía client-credentials OAuth2. | Activa, no específica de `daily`. |

## 3.3 Vecinos internos (dentro de esta plataforma)

| App | Rol respecto a `daily` |
|---|---|
| `apps/daily` | Reportes de solo lectura sobre el dominio (hoy: despacho policial). Sin auth propia — usa la cadena de autenticación global. |
| `apps/users` | Dueño de la identidad del operador: login/logout, reclamo de estación, sesión de turno. Dueño del nuevo esquema JWT ([ADR-0001](decisions/0001-jwt-desacoplado-de-usuarios-django.md)). |
| `apps/platform` | Login central (sin estación) para herramientas conectadas a la plataforma — comparte la misma tabla `daily_users` y, tras el ADR-0001, el mismo esquema JWT que `apps/users`. |
| `apps/core` | Modelos `managed=False` que mapean el esquema legacy (`User`, `UserRole`, `UserName`, `StationMap`) — fuente de verdad compartida por `daily`, `users` y `platform`. También el middleware `DailyUserMiddleware`. |
| `apps/sigtools_auth` | Esquema de autenticación independiente (cookie + LDAP) para el portal web de otras herramientas — corre en la misma cadena de autenticación de DRF, primero que la de `daily`. |

## 3.4 Alcance de este módulo (qué SÍ y qué NO)

- **Sí**: autenticación del dominio daily (operadores + login central de platform), reportes de solo lectura ya existentes (despacho policial).
- **No, todavía**: el resto del dominio Supabase (eventos, sitios, actividades, coberturas, splits, especiales de supervisor) — se aborda de forma incremental, documentado conforme se llegue ahí (ver [ADR-0002](decisions/0002-django-como-orquestador-reemplazo-supabase.md)).
- **No, nunca (decidido)**: revivir `daily-log-backend/`.
