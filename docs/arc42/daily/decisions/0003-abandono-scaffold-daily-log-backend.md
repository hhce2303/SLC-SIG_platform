# 0003. Abandono del scaffold paralelo `daily-log-backend`

**Estado:** Aceptada

**Fecha:** 2026-08-09

## Contexto

Dentro del repo **SIGDailyReport** (`Documents\GitHub\SIGDailyReport\daily-log-backend/`) existe un segundo backend Django/DRF, independiente de esta plataforma: Django ≥5.1, DRF, `djangorestframework-simplejwt`, apuntando también a la base MySQL legacy `sig_dailylogs` (mismas 4 DBs conceptuales: default/inventory/schedules/sigtools, con sus propios routers). Tiene solo **2 commits, ambos de 2026-05-08** ("primer commit, aún no se ha probado la funcionalidad"), y no se ha tocado desde entonces — nunca llegó a desplegarse ni a probarse.

Mantener dos backends Django independientes apuntando al mismo dominio (`sig_dailylogs`) es una fuente evidente de confusión y divergencia: cualquiera que lo redescubra podría asumir que es el camino activo.

## Decisión

Se **abandona explícitamente** `SIGDailyReport/daily-log-backend/`. `apps/daily` (junto con `apps/users`, `apps/platform` y el resto de esta plataforma) es el **único backend Django** del dominio daily desde ahora.

## Consecuencias

- Ningún código de `daily-log-backend/` se porta automáticamente a esta plataforma.
- Si en el futuro algo puntual de ese scaffold resulta útil como referencia (por ejemplo, algún serializer o vista ya pensada para este dominio), se evalúa caso por caso y se documenta explícitamente por qué se reutiliza — no se asume que el scaffold completo sigue siendo válido.
- Esta plataforma ya tiene la infraestructura viva que ese scaffold nunca llegó a tener en producción: routers de DB, esquema de autenticación multi-scheme, Docker/CI de despliegue, reglas de seguridad de datos. No hay razón técnica para reactivarlo en vez de seguir extendiendo `apps/daily`.
