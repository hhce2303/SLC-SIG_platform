# 6. Vista de Tiempo de Ejecución — Módulo `daily`

## 6.1 Escenario: login de operador (con estación)

`POST /api/v1/auth/login/` — `apps/users/views.py::LoginView` → `services.login()`:

```
Cliente                 LoginView            services.login()          DB (sig_dailylogs)
  │  POST login/            │                       │                        │
  ├─────────────────────────►                       │                        │
  │                         ├───────────────────────►                        │
  │                         │   1. UserName.objects.get(user_name=...)       │
  │                         │       (daily_users_names → user_id)     ───────►
  │                         │◄──────────────────────────────────────────────┤
  │                         │   2. DailyUser.objects.get(pk=user_id)         │
  │                         │       + validar password (texto plano)  ───────►
  │                         │◄──────────────────────────────────────────────┤
  │                         │   3. _claim_station(user_id, station_id)       │
  │                         │       (transacción, select_for_update) ───────►
  │                         │   4. _create_session(user_id, station_id)      │
  │                         │       (abre fila en daily_sesions)     ───────►
  │                         │   5. DailyAccessToken() + set_exp(~10y)        │
  │                         │       claims: daily_user_id, role              │
  │◄────────────────────────┤ {"access": "...", "refresh": null, ...}        │
```

Errores esperados: `ServiceException` (credenciales inválidas → 400), `ConflictError` (estación ocupada o usuario ya con sesión activa → 409), `ResourceNotFound` (estación inexistente → 404).

## 6.2 Escenario: login central de platform (sin estación)

`POST /api/v1/platform/auth/login/` — mismo patrón que 6.1 pero sin pasos 3/4 (no reclama estación ni abre sesión de turno). Post-[ADR-0001](decisions/0001-jwt-desacoplado-de-usuarios-django.md), emite el mismo tipo de token (`DailyAccessToken`) con claim adicional `platform: true`, y devuelve además el catálogo de tools accesibles (`get_user_tools()`).

## 6.3 Escenario: request autenticado (después del login)

Dos resoluciones de identidad ocurren en paralelo, en capas distintas, para el mismo request:

```
Request con "Authorization: Bearer <token>"
        │
        ├──► [Middleware, capa Django — antes de DRF]
        │     DailyUserMiddleware._resolve_user_pk()
        │       → decodifica token["daily_user_id"] directo
        │       → cachea/lee apps.core.models.User (Redis, 60s)
        │       → request.daily_user = User | None
        │
        └──► [DRF authentication chain — dentro de la vista]
              1. SigtoolsCookieAuthentication.authenticate()
                   → no hay cookie sig_token → return None
              2. DailyJWTAuthentication.authenticate()
                   → Bearer presente, .count(".")==2 → decodifica
                   → claim daily_user_id presente → lo resuelve
                   → return (DailyJWTUser(...), token)
              3. (JWTAuthentication genérico no se llega a evaluar
                   porque el paso 2 ya autenticó)
              → request.user = DailyJWTUser(...)
```

Nota: si el token es de otro esquema (p. ej. uno genérico sin `daily_user_id`), el paso 2 debe devolver `None` (no lanzar excepción) para que el paso 3 tenga la oportunidad de resolverlo — este es el comportamiento que ADR-0001 marca como obligatorio para no romper otros consumidores JWT de la plataforma.

## 6.4 Escenario: logout

`POST /api/v1/auth/logout/` → `services.logout()`: cierra la sesión activa (`_close_session`) y libera la estación (`_free_station`), en una transacción. **No revoca el access token** — sigue siendo válido hasta su expiración natural (~10 años). Ver riesgo #2 en [11_risks_and_technical_debt.md](11_risks_and_technical_debt.md).
