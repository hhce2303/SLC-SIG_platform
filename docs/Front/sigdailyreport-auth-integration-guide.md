# Guía de integración futura — Auth de SIGDailyReport → Django (SLC-SIG platform)

> ⚠️ **Este contrato NO está disponible todavía.** El código vive en 4 ramas locales del repo `SLC-SIG_platform` (`feature/daily-jwt-core`, `feature/daily-jwt-platform-login`, `feature/daily-jwt-usertoolaccess-fk`, `feature/daily-jwt-token-epoch`) — **sin pushear, sin PR, sin mergear a `main`, sin desplegar**. Nada de lo documentado acá es alcanzable por HTTP hoy. Este documento es preparación anticipada para cuando se aborde la fase de integración real descrita en [ADR-0002](../arc42/daily/decisions/0002-django-como-orquestador-reemplazo-supabase.md) — no hay fecha comprometida. **No cambiar nada en el código de SIGDailyReport a partir de este documento todavía.**

## 1. Por qué existe este documento

SIGDailyReport hoy corre 100% sobre **Supabase** (Auth + Postgres + RPCs). La plataforma SLC-SIG (este repo) va a reemplazar ese backend de forma incremental, empezando por el contrato de autenticación — ver [ADR-0001](../arc42/daily/decisions/0001-jwt-desacoplado-de-usuarios-django.md) para el diseño completo y [ADR-0002](../arc42/daily/decisions/0002-django-como-orquestador-reemplazo-supabase.md) para la dirección general. El objetivo de este documento es que el equipo de SIGDailyReport tenga por escrito, con anticipación, el contrato exacto que van a tener que consumir — para que puedan planear, no para que empiecen a integrar ya.

## 2. Correspondencia de flujos — lo que ya coincide

El login actual de SIGDailyReport (`src/features/auth/api.ts`) hace, en este orden: `resolveEmail(username)` → `supabase.auth.signInWithPassword()` → RPC `rpc_login_claim_station({p_station_id})` → RPC `rpc_me`. El nombre de esa RPC no es casualidad: **el flujo "Daily" de este backend Django ya resuelve exactamente lo mismo** — reclamar una estación y devolver el perfil — con la misma forma conceptual (usuario + estación → sesión de turno). Esto sugiere que, cuando llegue la fase de integración real, el login operativo de SIGDailyReport mapea al flujo `/api/v1/auth/login/` de abajo, no al flujo "Platform" (que es para herramientas centrales sin estación). Esta correspondencia es una observación para facilitar el diseño futuro, no una decisión ya tomada — se confirma cuando se aborde esa fase de ADR-0002.

## 3. El cambio de fondo: no hay que manejar refresh

Esto es lo más importante para el equipo de frontend. Hoy, el SDK de Supabase (`persistSession`/`autoRefreshToken`) maneja el refresh de sesión automáticamente y de forma transparente — el frontend nunca piensa en esto. **El nuevo contrato de Django no usa refresh tokens en absoluto**: el `access` token vive ~10 años y `refresh` siempre viene `null` en la respuesta de login. No hay endpoint de refresh, no hay rotación, no hay que configurar un interceptor. Se guarda el `access` una vez y se manda en cada request — punto.

Esto es una decisión deliberada, no una limitación: nace de un incidente real de operadores perdiendo sesión a mitad de turno con el esquema JWT corto+refresh que sí existe hoy en otra parte de esta plataforma (ver ADR-0001 §Contexto). La contrapartida es que la revocación no es instantánea por defecto — ver §6.

## 4. Contrato — Flujo "Daily" (con estación)

Corresponde al login operativo de un operador (ver §2).

**Base path:** `/api/v1/auth/`

| Método | Endpoint | Requiere token | Uso |
|--------|----------|----------------|-----|
| POST | `/login/` | No | Login con estación |
| POST | `/logout/` | Sí | Cerrar sesión y liberar estación (no revoca el token) |
| GET | `/me/` | Sí | Perfil y sesión activa |
| PATCH | `/me/status/` | Sí | Actualizar estado (0=offline, 1=active, 2=available-for-cover) |
| GET | `/stations/available/` | No | Estaciones libres |

**Request de login:**
```json
{
  "username": "operador1",
  "password": "1234",
  "station_id": 43
}
```

**Response de login `200 OK`:**
```json
{
  "access": "jwt-access-token",
  "refresh": null,
  "user": {
    "id": 25,
    "name": "operador1",
    "role": "Operador",
    "role_id": 2
  },
  "session_id": 912,
  "station_id": 43
}
```

`refresh` viene **siempre** `null` — no es un caso de error, es el contrato. Cada request autenticado usa:

```http
Authorization: Bearer <access>
```

## 5. Contrato — Flujo "Platform" (sin estación)

Login central para herramientas conectadas a la plataforma (catálogo de tools, sin sesión de turno). Documentado acá por completitud — ver §2 sobre por qué el flujo "Daily" es el que probablemente aplica al login operativo de SIGDailyReport.

**Base path:** `/api/v1/platform/`

| Método | Endpoint | Requiere token | Uso |
|--------|----------|----------------|-----|
| POST | `/auth/login/` | No | Login sin estación |
| GET | `/tools/` | Sí | Herramientas activas del usuario |

**Response de login `200 OK`:**
```json
{
  "access": "jwt-access-token",
  "refresh": null,
  "user": { "id": 8, "name": "supervisor1", "role": "Supervisor", "role_id": 3 },
  "tools": [ { "slug": "daily-log", "name": "Daily Log", "frontend_url": "...", "icon": "clipboard" } ]
}
```

Mismo contrato de `refresh: null` que el flujo Daily.

## 6. Lo que el equipo de frontend puede simplificar (cuando llegue el momento)

Comparado con el manejo actual de sesión de Supabase:

| Hoy (Supabase) | Futuro (Django, este contrato) |
|---|---|
| SDK maneja access + refresh automáticamente | Solo `access`, se guarda una vez, no expira en la práctica |
| `onAuthStateChange` para detectar expiración/logout forzado | No hay expiración que detectar en el uso normal |
| Interceptor de refresh silencioso | No aplica — no existe endpoint de refresh |
| Revocación vía Supabase Auth (inmediata) | Revocación vía `daily_token_epoch` (ver abajo) — no instantánea por defecto en el mismo segundo, pero sí completa (todos los tokens de un operador de una vez) |

**Sobre revocación:** si un token se filtra, un administrador puede revocar todos los tokens de ese operador (tabla `daily_token_epoch`, ver [ADR-0001 punto 7](../arc42/daily/decisions/0001-jwt-desacoplado-de-usuarios-django.md)) — hoy eso se hace desde Django admin, no hay endpoint REST dedicado todavía. `logout` (§4) **no** revoca el token, solo cierra la sesión/estación en base de datos — el `access` sigue funcionando hasta que se revoque explícitamente o expire (~10 años).

## 7. Qué NO cubre este documento

- Los endpoints de negocio (eventos, sitios, actividades, coberturas, specials, splits) — esos son fases posteriores de ADR-0002, sin contrato definido todavía.
- Cualquier cambio real en el código de SIGDailyReport — cero, por ahora.
- Fecha de la migración real — no está comprometida.

## Referencias

- [ADR-0001 — JWT desacoplado de `django.contrib.auth.User`](../arc42/daily/decisions/0001-jwt-desacoplado-de-usuarios-django.md) — diseño técnico completo del contrato.
- [ADR-0002 — Django como orquestador, reemplazo de Supabase](../arc42/daily/decisions/0002-django-como-orquestador-reemplazo-supabase.md) — dirección y alcance general de la migración.
- [manual-conexion-milestones.md](manual-conexion-milestones.md) — mismo contrato, documentado para el equipo interno que ya consume `/auth/` y `/platform/auth/` hoy.
