# 0002. Django como orquestador — reemplazo de Supabase para el dominio daily

**Estado:** Aceptada (dirección estratégica) — alcance de implementación pendiente de detallar por fases

**Fecha:** 2026-08-09

## Contexto

El frontend **SIGDailyReport** (repo aparte, `Documents\GitHub\SIGDailyReport`, React + TS + Vite) corre hoy **100% sobre Supabase**: Auth propio (con una capa de usuario/estación encima), ~60 tablas Postgres repartidas en dos proyectos Supabase (`daily` y `splits`), un buen número de RPCs `SECURITY DEFINER` como capa de servicio, Realtime (`postgres_changes`) para varias features, y una edge function (`site-connectivity-check`, poll cada 2 min vía `pg_cron`/`pg_net`).

El dominio de esas tablas (`daily_users`, `daily_events`, `daily_sites`, `daily_activities`, `daily_covers_*`...) **coincide en nombre y forma** con la base MySQL legacy `sig_dailylogs`, que esta plataforma (SLC-SIG platform) ya usa como DB `default` para `apps/daily`, `apps/users` y `apps/platform`. Es la misma familia de dominio, migrada una vez de MySQL a Supabase para el frontend, y parcialmente presente todavía del lado Django/MySQL.

Dentro del propio repo de SIGDailyReport existe además un backend Django/DRF paralelo (`daily-log-backend/`) que intentó atacar este mismo problema apuntando a `sig_dailylogs` directamente — abandonado sin llegar a producción (ver [ADR-0003](0003-abandono-scaffold-daily-log-backend.md)).

## Decisión

**SLC-SIG platform (`apps/daily`, `apps/users`, y los módulos que se sumen) es el backend de destino para el dominio daily.** Django orquesta autenticación, reglas de negocio, acceso a datos y tiempo real, reemplazando a Supabase de forma **incremental**, no en un solo corte.

**Alcance de esta fase (la única resuelta hasta ahora):** dirección estratégica + contrato de autenticación ([ADR-0001](0001-jwt-desacoplado-de-usuarios-django.md)). **Cero cambios de código en SIGDailyReport todavía** — ese repo se usa solo como referencia de dominio (esquema, RPCs, flujo de auth) para diseñar los futuros modelos/endpoints Django.

## Consecuencias

- El trabajo futuro (no planificado en detalle todavía, se documenta conforme se aborde) incluye:
  - Mapear las ~60 tablas Supabase a modelos/tablas equivalentes accesibles desde Django (evaluar si conviene seguir usando `sig_dailylogs`/MySQL o si algunas piezas nuevas ameritan Postgres).
  - Portar las RPCs `SECURITY DEFINER` (`rpc_login_claim_station`, `rpc_me`, `rpc_logout*`, la familia `eos_*`, `zone_*`, `rpc_site_connectivity_*`, etc.) a endpoints DRF / funciones de servicio equivalentes.
  - Reemplazar la edge function `site-connectivity-check` por un job Celery/cron — la plataforma ya tiene Redis y patrones de tareas periódicas que se pueden reutilizar.
  - Reemplazar Realtime (`postgres_changes`) por el mecanismo SSE que esta plataforma ya expone (`GET /api/v1/inventory/stream/`, `/installations/stream/`, vía Redis pub/sub) — mismo patrón, nuevo canal.
  - Eventualmente, migrar el frontend SIGDailyReport para que sus llamadas `supabase.from()/.rpc()/.auth.*` apunten a la nueva API Django — fase explícitamente fuera de alcance por ahora.
- No se compromete una fecha ni un orden de estas piezas en este ADR — cada una se documenta con su propia decisión cuando se aborde, como pidió el stakeholder ("conforme avancemos en la documentación iremos rellenando esos contextos").
