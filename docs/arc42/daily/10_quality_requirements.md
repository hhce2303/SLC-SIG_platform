# 10. Requisitos de Calidad — Módulo `daily`

## 10.1 Árbol de calidad

Ranking ya fijado en [goals.md](goals.md) §1.2: **continuidad operativa** > **un solo backend por dominio** > **consistencia con la plataforma**.

## 10.2 Escenarios de calidad

| # | Escenario | Meta relacionada | Respuesta esperada del sistema |
|---|---|---|---|
| 1 | Un operador inicia turno a las 08:00 y lo termina a las 20:00 (turno de 12h), sin volver a autenticarse. | Continuidad operativa | El access token (~10 años de vida) sigue siendo válido durante todo el turno — cero prompts de re-login, sin necesidad de refresh token. |
| 2 | Un desarrollador nuevo busca "dónde está el backend de daily" y encuentra tanto `apps/daily` como `SIGDailyReport/daily-log-backend/`. | Un solo backend por dominio | [ADR-0003](decisions/0003-abandono-scaffold-daily-log-backend.md) responde inequívocamente cuál es el vigente y por qué el otro se descartó. |
| 3 | Se necesita agregar un nuevo endpoint de reporte en `apps/daily`. | Consistencia con la plataforma | El desarrollador puede copiar el patrón `selectors.py`/`serializers.py`/`views.py` de `PoliceDispatchListView` sin inventar una convención nueva. |
| 4 | Un token de daily se filtra (ej. dispositivo robado). | (trade-off aceptado, ver riesgo #1) | No hay revocación fina disponible en v1 — el operador afectado se maneja borrando su fila en `daily_users` o, en el peor caso, rotando `SECRET_KEY` (afecta a toda la plataforma). Ver [11_risks_and_technical_debt.md](11_risks_and_technical_debt.md). |
| 5 | Se despliega una migración nueva (ej. `UserToolAccess.user` → FK a `apps.core.models.User`). | Consistencia con la plataforma / seguridad de datos | Se prueba primero en local `mysql:8.0` (nunca MariaDB), con backup antes de aplicar en producción, siguiendo el checklist de DB safety de la plataforma. |

## 10.3 Trade-off explícito

Se prioriza **disponibilidad de sesión** sobre **capacidad de revocación fina** — es la consecuencia directa y aceptada de "el token no debe forzar el cierre del frontend". Cualquier trabajo futuro que quiera añadir revocación (ver riesgo #1) debe hacerlo sin reintroducir expiraciones cortas ni refresh tokens obligatorios, o estaría revirtiendo esta meta de calidad sin decirlo.
