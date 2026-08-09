# 9. Decisiones de Arquitectura — Módulo `daily`

Bitácora de Architecture Decision Records (ADR) de este módulo. Cada decisión arquitectónica se documenta acá antes de implementarse, usando la [plantilla](decisions/TEMPLATE.md) (formato Nygard).

| ADR | Título | Estado | Fecha |
|---|---|---|---|
| [0001](decisions/0001-jwt-desacoplado-de-usuarios-django.md) | JWT desacoplado de `django.contrib.auth.User` para operadores daily (y platform) | Aceptada | 2026-08-09 |
| [0002](decisions/0002-django-como-orquestador-reemplazo-supabase.md) | Django como orquestador — reemplazo de Supabase para el dominio daily | Aceptada (dirección estratégica) | 2026-08-09 |
| [0003](decisions/0003-abandono-scaffold-daily-log-backend.md) | Abandono del scaffold paralelo `daily-log-backend` | Aceptada | 2026-08-09 |

Para agregar una nueva decisión: copiar `decisions/TEMPLATE.md`, numerar correlativo (`0004-...`), y agregar la fila correspondiente a esta tabla.
