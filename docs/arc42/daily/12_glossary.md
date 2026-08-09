# 12. Glosario — Módulo `daily`

| Término | Significado |
|---|---|
| Operador | Usuario humano de `daily_users` que trabaja un turno en una estación del centro de monitoreo. |
| Supervisor / Lead Supervisor / Admin | Roles con permisos elevados sobre el operador base (`apps.core.permissions.IsSupervisor`, `IsLeadSupervisor`, `IsAdmin`). |
| Estación | Puesto físico de trabajo (`StationMap`/`daily_stations_map`), reclamado por un operador al iniciar sesión; se libera al cerrar sesión. |
| Sesión (BD) | Registro de turno activo (`Session`/`daily_sesions`) — **no** confundir con la "sesión" de autenticación: el JWT no expira en la práctica (~10 años), pero la sesión de BD sí se abre/cierra por turno. |
| Platform (login central) | Login sin estación (`apps/platform`) usado por herramientas conectadas a la plataforma (installations, inventory, etc.), no específico de un turno de Daily Log. |
| Tool | Una herramienta/aplicación conectada al login central de platform (`platform_tools`), con acceso configurable por operador (`UserToolAccess`). |
| Despacho policial (Police Dispatch) | Reporte de solo lectura sobre eventos con `ID_activity = 23` en `daily_events` — el único endpoint que expone `apps/daily` hoy. |
| Especial (Special) | Aviso de supervisor que requiere confirmación de lectura (`apps/notifications`) — parte del dominio daily más amplio, aún no migrado. |
| Cover | Solicitud/cobertura de turno entre operadores (`daily_covers_*`) — parte del dominio daily más amplio, aún no migrado. |
| Splits | Módulo separado del dominio SIGDailyReport (proyecto Supabase propio, sin autenticación) — asignación de turnos/estaciones por aplicación. Fuera de alcance de esta fase. |
| SIGDailyReport | Frontend React+TS+Vite del dominio daily, hoy sobre Supabase — repo aparte, futuro consumidor de este backend. |
| `daily-log-backend` | Scaffold Django/DRF abandonado dentro del repo de SIGDailyReport — ver [ADR-0003](decisions/0003-abandono-scaffold-daily-log-backend.md). |
| `sig_dailylogs` | Base de datos MySQL legacy (alias Django `default`) que es la fuente de verdad de todo el dominio daily dentro de esta plataforma. |
| RPC `SECURITY DEFINER` | Función de Postgres (Supabase) que ejecuta con privilegios elevados, usada como capa de servicio en el sistema actual — equivalente conceptual a `services.py` en Django. |
