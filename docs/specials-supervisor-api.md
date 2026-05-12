# Manual de conexión — Supervisor Specials API

**Base URL:** `http://<host>:8000/api/v1`  
**Autenticación:** JWT Bearer token (obtenido en `/api/v1/auth/login/`)  
**Roles requeridos:** Supervisor, Lead Supervisor, Admin

---

## 1. Autenticación

Todos los endpoints de specials requieren el header:

```http
Authorization: Bearer <access_token>
```

El access token se obtiene en el login y expira según `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` (default 60 min). Refresca con `/api/v1/auth/token/refresh/`.

---

## 2. Endpoints disponibles

### 2.1 `GET /api/v1/specials/supervisor/`

Lista los specials pendientes asignados al supervisor autenticado.  
**Excluye** los que tienen `spec_status = 'done'`. Incluye los que tienen `spec_status = null` o `spec_status = 'flagged'`.

#### Request

```http
GET /api/v1/specials/supervisor/ HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Sin body, sin query params.

#### Response `200 OK`

```json
{
  "data": [
    {
      "id": 1042,
      "spec_datetime": "2026-04-21T08:35:00Z",
      "site_id": 17,
      "site_name": "Sitio Ejemplo Norte",
      "site_timezone": "America/Chicago",
      "act_name": "Actividad especial",
      "spec_quantity": "3",
      "spec_camera": "CAM-04",
      "spec_description": "Persona sospechosa en perímetro",
      "operator_name": "Juan Perez",
      "spec_status": null,
      "spec_marked_by": null,
      "spec_marked_at": null
    },
    {
      "id": 1039,
      "spec_datetime": "2026-04-21T07:12:00Z",
      "site_id": 22,
      "site_name": "Sitio Sur B",
      "site_timezone": "America/New_York",
      "act_name": "Alarma perimetral",
      "spec_quantity": "1",
      "spec_camera": "CAM-01",
      "spec_description": "Alarma activada sin causa aparente",
      "operator_name": "Maria Lopez",
      "spec_status": "flagged",
      "spec_marked_by": 5,
      "spec_marked_at": "2026-04-21T07:45:00Z"
    }
  ],
  "total": 2
}
```

#### Campos del objeto Special

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `number` | ID único del special |
| `spec_datetime` | `string (ISO 8601)` | Fecha/hora del evento en UTC |
| `site_id` | `number` | ID del sitio |
| `site_name` | `string \| null` | Nombre del sitio |
| `site_timezone` | `string \| null` | Timezone del sitio (ej. `America/Chicago`) |
| `act_name` | `string \| null` | Nombre de la actividad |
| `spec_quantity` | `string \| null` | Cantidad registrada |
| `spec_camera` | `string \| null` | Cámara asociada |
| `spec_description` | `string \| null` | Descripción del evento |
| `operator_name` | `string \| null` | Nombre del operador que creó el special |
| `spec_status` | `"done" \| "flagged" \| null` | Estado actual |
| `spec_marked_by` | `number \| null` | ID del supervisor que marcó |
| `spec_marked_at` | `string (ISO 8601) \| null` | Fecha/hora en que fue marcado (UTC) |

#### Errores

| Status | Cuándo |
|--------|--------|
| `401 Unauthorized` | Token inválido, expirado o ausente |
| `403 Forbidden` | El usuario autenticado no tiene rol Supervisor+ |

---

### 2.2 `PATCH /api/v1/specials/{id}/mark/`

Marca o desmarca un special. Solo el supervisor al que está **asignado** puede ejecutarlo.

#### Casos de uso

| Acción | Body |
|--------|------|
| Marcar como revisado | `{ "status": "done" }` |
| Marcar como en progreso | `{ "status": "flagged" }` |
| Desmarcar (limpiar) | `{ "status": null }` |

#### Request — marcar como done

```http
PATCH /api/v1/specials/1042/mark/ HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "status": "done"
}
```

#### Request — desmarcar

```http
PATCH /api/v1/specials/1042/mark/ HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "status": null
}
```

#### Response `200 OK`

El objeto Special actualizado con los mismos campos que en la lista:

```json
{
  "id": 1042,
  "spec_datetime": "2026-04-21T08:35:00Z",
  "site_id": 17,
  "site_name": "Sitio Ejemplo Norte",
  "site_timezone": "America/Chicago",
  "act_name": "Actividad especial",
  "spec_quantity": "3",
  "spec_camera": "CAM-04",
  "spec_description": "Persona sospechosa en perímetro",
  "operator_name": "Juan Perez",
  "spec_status": "done",
  "spec_marked_by": 5,
  "spec_marked_at": "2026-04-21T14:22:00Z"
}
```

#### Errores

| Status | Cuándo |
|--------|--------|
| `400 Bad Request` | Body inválido o `status` con valor no permitido |
| `401 Unauthorized` | Token inválido, expirado o ausente |
| `403 Forbidden` | El usuario no tiene rol Supervisor+ |
| `404 Not Found` | El special no existe o no está asignado al supervisor autenticado |

---

## 3. Flujo de integración recomendado

```
Supervisor abre su pantalla de specials
    │
    ▼
GET /api/v1/specials/supervisor/
    ├─ Renderiza tabla con los specials pendientes
    └─ Guarda un timestamp de la última consulta
    
Usuario hace clic en "Marcar como revisado" sobre una fila
    │
    ▼
PATCH /api/v1/specials/{id}/mark/   { "status": "done" }
    ├─ 200 OK → actualiza la fila en pantalla (o la elimina si se filtra 'done')
    └─ 404    → aviso: "Este special ya no está asignado a ti"

[Opcional] Polling para actualizaciones en vivo
    └─ Intervalo mínimo recomendado: 30 segundos
       (NO usar intervalos menores: el backend comparte DB con otros módulos)
```

---

## 4. Consideraciones de rendimiento

- **Una sola query por `GET`:** el backend hace un SELECT con JOINs a `daily_sites`, `daily_activities` y `daily_users_names`. No hay queries adicionales por fila.
- **Intervalo de polling:** si el frontend necesita refrescar la lista periódicamente, usa un intervalo ≥ 30 s. Para refresco en tiempo real, esperar la implementación del WebSocket channel `ws/notifications/{user_id}/`.
- **Optimistic UI en mark:** tras hacer `PATCH`, actualiza la fila en el estado local inmediatamente con la respuesta recibida — no necesitas refrescar toda la lista.

---

## 5. Ejemplo de integración (Fetch API)

```javascript
const BASE_URL = import.meta.env.VITE_API_URL; // 'http://localhost:8000/api/v1'

async function fetchSupervisorSpecials(accessToken) {
  const res = await fetch(`${BASE_URL}/specials/supervisor/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const { data, total } = await res.json();
  return data; // Special[]
}

async function markSpecial(accessToken, specialId, status) {
  // status: 'done' | 'flagged' | null
  const res = await fetch(`${BASE_URL}/specials/${specialId}/mark/`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ status }),
  });
  if (res.status === 404) throw new Error('Special no disponible');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json(); // Special actualizado
}
```

---

## 6. Swagger interactivo

Todos los endpoints están documentados en OpenAPI:

- **UI:** `http://localhost:8000/api/docs/`
- **Schema JSON:** `http://localhost:8000/api/schema/`
