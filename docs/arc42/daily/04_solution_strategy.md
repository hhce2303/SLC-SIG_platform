# 4. Estrategia de Solución — Módulo `daily`

## 4.1 Decisiones tecnológicas clave

| Decisión | Por qué |
|---|---|
| Resolver primero el contrato de autenticación, antes que cualquier endpoint de negocio | Todo lo demás depende de tener una identidad estable. Endpoints de negocio construidos sobre un esquema de auth que cambia son más caros de retrabajar que esperar a fijar el contrato primero. Ver [ADR-0001](decisions/0001-jwt-desacoplado-de-usuarios-django.md). |
| Reutilizar `sig_dailylogs` (MySQL) como fuente de verdad, no migrar a Postgres | Ya es la base de datos legacy que alimenta tanto el sistema de escritorio original (`proyecto_app`) como el resto de esta plataforma. Migrar de motor sería un proyecto aparte, no justificado todavía. |
| Imitar el patrón `SigtoolsCookieAuthentication`/`SigtoolsWebUser` en vez de inventar uno nuevo | Es el único precedente ya probado en esta plataforma de un `BaseAuthentication` custom que no depende de `auth.User`. Reduce superficie de bugs nuevos y mantiene consistencia de estilo. |
| Migrar `apps/platform` en la misma tanda que `apps/users`, no dejarlo como excepción | Ambos dependían del mismo `DailyUserBackend`; dejarlo vivo solo para uno de los dos habría sido una coexistencia parcial, justo lo que el stakeholder pidió evitar. |
| Reemplazo de Supabase incremental, no big-bang | ~60 tablas + RPCs `SECURITY DEFINER` + Realtime + edge function es demasiada superficie para un solo corte. Se documenta y ataca por partes, cada una con su propio ADR cuando se aborde. |
| Sin cambios en SIGDailyReport todavía | El frontend sigue funcionando sobre Supabase mientras se construye el reemplazo — cero riesgo de interrumpir el sistema en producción durante esta fase. |

## 4.2 Patrones de arquitectura heredados de la plataforma

- **Capas por app**: `views.py` (delgado) → `serializers.py` → `services.py`/`selectors.py` → modelos (o SQL crudo contra tablas legacy). Ningún acceso directo a `Model.objects.*` desde vistas o serializers.
- **Autenticación en cadena**: DRF prueba varios `BaseAuthentication` en orden (`SigtoolsCookieAuthentication` → `DailyJWTAuthentication` → `JWTAuthentication` genérico) y cada uno debe devolver `None` (no lanzar excepción) cuando el token/cookie no le corresponde, para no cortar la cadena y dejar sin acceso a los demás esquemas.
- **Identidad resuelta dos veces, en dos capas distintas**: `DailyUserMiddleware` (capa Django, antes de DRF) para código no-DRF (SSE, permisos basados en `request.daily_user`), y el authenticator DRF (para `request.user` dentro de vistas). Ambos comparten la misma caché Redis por diseño.

## 4.3 Qué NO se hizo (y por qué)

- No se introdujo un modelo de usuario custom (`AUTH_USER_MODEL`) — habría sido un cambio de framework mucho más invasivo que resolver el problema a nivel de `BaseAuthentication`.
- No se construyó una tabla de revocación (denylist) para v1 — se aceptó el riesgo documentado en [11_risks_and_technical_debt.md](11_risks_and_technical_debt.md) en vez de añadir complejidad sin un caso de uso concreto todavía.
