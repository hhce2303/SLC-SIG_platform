# 5. Vista de Bloques de Construcción — Módulo `daily`

## 5.1 Nivel 1 — Apps involucradas

```
┌────────────────────────────────────────────────────────────────┐
│                         DB "default" (sig_dailylogs, MySQL)      │
│  daily_users · daily_users_names · daily_user_rol ·              │
│  daily_stations_info · daily_stations_map · daily_sesions ·      │
│  daily_events · daily_activities · platform_tools ·              │
│  platform_user_tool_access                                       │
└────────────────────────────────────────────────────────────────┘
        ▲                    ▲                     ▲
        │ managed=False      │ managed=False        │ FK (post ADR-0001:
        │ lecturas            │ lecturas/escrituras │  db_constraint=False)
        │                    │                     │
┌───────┴──────┐    ┌────────┴───────┐    ┌────────┴────────┐
│  apps/core    │    │  apps/users     │    │  apps/platform   │
│  (modelos     │◄───┤  (identidad,    │    │  (login central, │
│  compartidos  │    │  login/logout,  │    │  catálogo tools) │
│  + middleware)│    │  estación,      │    │                  │
│               │    │  sesión)        │    └──────────────────┘
└───────┬──────┘    └────────┬───────┘
        │                    │
        │ selectors.py       │ authentication.py (nuevo, ADR-0001)
        ▼                    ▼
┌──────────────┐    ┌─────────────────────────────┐
│  apps/daily   │    │  DailyJWTAuthentication /    │
│  (reportes    │    │  DailyJWTUser / DailyAccessToken │
│  read-only)   │    └─────────────────────────────┘
└──────────────┘
```

## 5.2 `apps/core` — modelos compartidos

| Componente | Rol |
|---|---|
| `apps.core.models.User` | `managed=False`, mapea `daily_users`. Fuente de verdad del operador — leído por `apps/users`, `apps/platform` y el middleware. |
| `apps.core.models.UserRole` | Rol del operador (Operador/Supervisor/Lead Supervisor/Admin). |
| `apps.core.models.UserName` | Resuelve `username` → `user_id` (tabla `daily_users_names`). |
| `apps.core.models.StationMap` | Estación física ocupada/libre — `station_user_id` nullable. |
| `apps.core.middleware.daily_user.DailyUserMiddleware` | Adjunta `request.daily_user` para código fuera de DRF (SSE, permisos por rol). Cacheado en Redis, 60s TTL. |

## 5.3 `apps/users` — identidad y sesión de turno

| Componente | Rol |
|---|---|
| `services.py::login()`/`logout()` | Orquesta: resolver username → validar password → reclamar estación → crear/cerrar sesión de turno → emitir/descartar token. |
| `services.py::_claim_station()`/`_free_station()` | Ocupar/liberar `StationMap`. |
| `services.py::_create_session()`/`_close_session()` | Abrir/cerrar fila en `Session` (`daily_sesions`). |
| `authentication.py` (nuevo, ADR-0001) | `DailyJWTAuthentication` (valida Bearer), `DailyJWTUser` (wrapper liviano), `DailyAccessToken` (subclase de `AccessToken` con vida ~10 años). |
| `models.py::Session` | Turno activo de un operador en una estación. |

## 5.4 `apps/platform` — login central

| Componente | Rol |
|---|---|
| `services.py::platform_login()` | Login sin estación, para herramientas conectadas (no específico de un turno de Daily Log). Post-ADR-0001, usa el mismo `DailyAccessToken`/`DailyJWTUser` que `apps/users`. |
| `services.py::get_user_tools()` | Política de acceso: si el operador tiene filas explícitas en `UserToolAccess`, solo esas; si no tiene ninguna, todas las tools activas (acceso abierto por defecto). |
| `models.py::Tool` | Catálogo de herramientas conectadas (`slug`, `frontend_url`, `is_active`). |
| `models.py::UserToolAccess` | Grant explícito operador↔tool. FK a `apps.core.models.User` (post-ADR-0001), antes FK dura a `auth.User`. |

## 5.5 `apps/daily` — reportes

| Componente | Rol |
|---|---|
| `selectors.py::get_police_dispatch_events()` | Lectura SQL cruda sobre `daily_events` filtrado por `ID_activity = 23` (Dispatched). |
| `serializers.py::PoliceDispatchReadSerializer` | Serializa el resultado del selector. |
| `views.py::PoliceDispatchListView` | `APIView`, `GET`, `IsAuthenticated` (hereda de la cadena de autenticación global — no tiene lógica de auth propia). |
| `urls.py` | `GET /api/v1/daily/police-dispatch/`. |

Sin modelos Django propios en `apps/daily` — todo el acceso a datos es vía `selectors.py` (SQL directo).
